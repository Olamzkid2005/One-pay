# Requirements Document

## Introduction

This document specifies the requirements for replacing the existing Quickteller/Interswitch payment API integration with KoraPay API across the entire OnePay application. The migration must maintain all existing payment functionalities while ensuring backward compatibility with the database schema, user interfaces, and external integrations. The system currently uses Quickteller for OAuth token management, virtual account creation for bank transfers, transfer confirmation polling, and mock mode support for testing.

This specification includes comprehensive performance targets, security constraints, scalability requirements, edge-case coverage, integration points, testing strategies, and deployment pipelines to ensure production-ready implementation with measurable success criteria.

### Performance Targets

- **Virtual Account Creation:** < 2 seconds (95th percentile), < 5 seconds (99th percentile)
- **Transfer Status Query:** < 1 second (95th percentile), < 3 seconds (99th percentile)
- **Webhook Processing:** < 500ms (95th percentile), < 1 second (99th percentile)
- **Database Queries:** < 100ms (95th percentile), < 250ms (99th percentile)
- **System Throughput:** 100 concurrent payment links/minute, 500 status polls/minute
- **Success Rate:** > 99.5% for all API operations (excluding provider outages)
- **Availability:** 99.9% uptime (excluding scheduled maintenance)

### Scalability Targets

- **Horizontal Scaling:** Support 10+ application instances with shared database
- **Database Connections:** Max 20 connections per instance, connection pooling enabled
- **Concurrent Transactions:** Handle 1000+ concurrent payment confirmations without data corruption
- **Peak Load:** Support 10x normal traffic during flash sales or promotional events
- **Storage Growth:** Support 1M+ transactions with query performance < 100ms

## Glossary

- **Payment_Gateway**: The external payment service provider (KoraPay) that processes payment transactions via REST API
- **Virtual_Account**: A temporary, single-use bank account number generated for a specific transaction with expiry time
- **Transaction**: A payment record in the OnePay database with a unique transaction reference (tx_ref)
- **Merchant**: A registered OnePay user who creates payment links and receives payments
- **Customer**: An end-user who makes a payment through a payment link via bank transfer
- **Mock_Mode**: A testing mode that simulates payment provider responses without real API credentials, auto-confirming after 3 polls
- **Webhook**: An HTTP POST callback that notifies the application of payment status changes with HMAC signature
- **Transfer_Confirmation**: The process of verifying that a bank transfer has been received by polling KoraPay API
- **Bearer_Token**: An API key used to authenticate requests to KoraPay (format: "Bearer sk_live_***" or "Bearer sk_test_***")
- **Transaction_Reference**: A unique merchant-generated identifier (tx_ref) for each payment transaction (min 8 characters)
- **Payment_Reference**: KoraPay's internal identifier for a transaction (format: "KPY-CA-***" or "KPY-PAY-***")
- **Payment_Link**: A secure, time-bound URL that customers use to make payments (format: /pay/{tx_ref})
- **Rate_Limiter**: A mechanism that restricts the number of API requests per time period to prevent abuse
- **Idempotency**: The property that multiple identical requests produce the same result without side effects
- **HMAC_Signature**: A cryptographic signature computed using HMAC-SHA256 to verify webhook authenticity
- **Kobo**: The smallest currency unit in Nigerian Naira (1 Naira = 100 Kobo) - NOT used by KoraPay
- **Major_Currency_Unit**: The standard currency unit (Naira) used by KoraPay API (e.g., 1500 for ₦1,500)
- **Configuration_Service**: The component that manages environment variables and API credentials from .env file
- **Database_Schema**: The structure of database tables and relationships (Transaction, User, AuditLog, Invoice)
- **Audit_Log**: A record of security-relevant events and actions with timestamp, user_id, event_type, and details
- **KoraPay_Service**: The service module that encapsulates all KoraPay API interactions
- **KoraPayError**: A custom exception raised when KoraPay API operations fail
- **Webhook_Handler**: The endpoint that receives and processes webhook notifications from KoraPay
- **Optimistic_Locking**: A database concurrency control technique using with_for_update() to prevent race conditions
- **Exponential_Backoff**: A retry strategy with increasing delays (1s, 2s, 4s) for transient failures
- **DNS_Rebinding**: A security attack where DNS resolution changes between validation and request
- **SSRF**: Server-Side Request Forgery attack where attacker tricks server into making requests to internal resources
- **Constant_Time_Comparison**: A cryptographic technique using hmac.compare_digest() to prevent timing attacks
- **Circuit_Breaker**: A pattern that stops calling a failing service after consecutive failures to prevent cascading failures
- **Round_Trip_Property**: A correctness property where parse(format(x)) == x for all valid inputs
- **Sandbox_Mode**: KoraPay test environment using test API keys (sk_test_*) with auto-complete feature
- **Production_Mode**: KoraPay live environment using live API keys (sk_live_*) for real transactions
- **Auto_Complete**: A sandbox-only feature that automatically triggers payment after 2 minutes for testing
- **Merchant_Bears_Cost**: A boolean flag indicating whether merchant pays transaction fees instead of customer
- **Notification_URL**: The webhook URL where KoraPay sends payment status notifications
- **Metadata**: Custom key-value pairs attached to transactions (max 5 fields, field names max 20 chars)
- **Narration**: Optional description text shown on bank transfer receipts
- **Account_Name**: The name displayed on the virtual bank account for customer transfers
- **Bank_Code**: Three-digit code identifying Nigerian banks (e.g., "035" for Wema Bank)
- **Expiry_Date**: UTC timestamp when virtual account expires and stops accepting transfers
- **Fee**: Transaction processing fee charged by KoraPay (in major currency units)
- **VAT**: Value-added tax on transaction fee (in major currency units)
- **Amount_Expected**: The exact amount KoraPay expects to receive (in major currency units)
- **Payer_Bank_Account**: Details of the customer's bank account used to make the transfer
- **Virtual_Bank_Account_Details**: Complete information about the generated virtual account
- **Event_Type**: The type of webhook event (charge.success, charge.failed, transfer.success, etc.)
- **Signature_Header**: HTTP header containing HMAC signature (x-korapay-signature)
- **Refund_Reference**: Unique identifier for a refund operation (max 50 characters)
- **Refund_Reason**: Optional explanation for refund (max 200 characters)
- **Refund_Status**: Status of refund operation (processing, failed, success)
- **Pagination_Cursor**: Token used for cursor-based pagination in list endpoints
- **Retry_After_Header**: HTTP header indicating seconds to wait before retrying rate-limited request
- **Connection_Pool**: Reusable HTTP connections to improve performance and reduce latency
- **Session_Object**: requests.Session instance for connection pooling and keep-alivebhook authenticity
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
### Requirement 3: Implement KoraPay Service Module with Complete API Integration

**User Story:** As a developer, I want a KoraPay service module that encapsulates all API interactions with complete error handling, retry logic, and security controls, so that payment logic is centralized, maintainable, and production-ready.

#### Acceptance Criteria

**Module Structure and Initialization:**

1. THE System SHALL create a new service module at services/korapay.py with class KoraPayService
2. THE KoraPay_Service SHALL initialize with no constructor parameters (credentials loaded from Config)
3. THE KoraPay_Service SHALL create a requests.Session instance in __init__ for connection pooling
4. THE KoraPay_Service SHALL configure the Session with HTTPAdapter using max_retries=0 (manual retry control)
5. THE KoraPay_Service SHALL configure the Session with pool_connections=10 and pool_maxsize=10 for connection reuse
6. THE KoraPay_Service SHALL set Session.headers with User-Agent "OnePay-KoraPay/1.0" for all requests
7. THE KoraPay_Service SHALL create a global singleton instance named korapay at module level
8. THE KoraPay_Service SHALL define custom exception class KoraPayError(Exception) at module level

**Authentication and Configuration:**

9. THE KoraPay_Service SHALL load KORAPAY_SECRET_KEY from Config for Bearer token authentication
10. THE KoraPay_Service SHALL construct Authorization header as f"Bearer {Config.KORAPAY_SECRET_KEY}"
11. THE KoraPay_Service SHALL select base URL from Config.KORAPAY_BASE_URL (production: https://api.korapay.com)
12. THE KoraPay_Service SHALL select base URL from Config.KORAPAY_SANDBOX_URL when Config.KORAPAY_USE_SANDBOX is True
13. THE KoraPay_Service SHALL implement method is_configured() returning bool(Config.KORAPAY_SECRET_KEY and len(Config.KORAPAY_SECRET_KEY) >= 32)
14. THE KoraPay_Service SHALL implement method is_transfer_configured() returning is_configured() (no additional config needed)
15. THE KoraPay_Service SHALL implement method _is_mock() returning not is_configured()
16. THE KoraPay_Service SHALL log "KoraPay configured in PRODUCTION mode" when KORAPAY_SECRET_KEY starts with "sk_live_"
17. THE KoraPay_Service SHALL log "KoraPay configured in TEST mode" when KORAPAY_SECRET_KEY starts with "sk_test_"
18. THE KoraPay_Service SHALL log "KoraPay MOCK MODE active - no real API calls" when _is_mock() returns True

**Virtual Account Creation - API Request:**

19. THE KoraPay_Service SHALL implement method create_virtual_account(transaction_reference: str, amount_naira: Decimal, account_name: str, customer_email: str, customer_name: str) -> dict
20. THE KoraPay_Service SHALL construct endpoint URL as f"{base_url}/merchant/api/v1/charges/bank-transfer"
21. THE KoraPay_Service SHALL use HTTP method POST for virtual account creation
22. THE KoraPay_Service SHALL convert amount_naira (Decimal) to integer by multiplying by 1 (KoraPay uses major units, not kobo)
23. THE KoraPay_Service SHALL validate amount is between 100 and 999999999 (₦100 to ₦999,999,999)
### Requirement 4: Implement Comprehensive Mock Mode for Testing

**User Story:** As a developer, I want a comprehensive mock mode that simulates all KoraPay API behaviors including success, failure, and edge cases, so that I can test the complete payment flow without real API credentials or external dependencies.

#### Acceptance Criteria

**Mock Mode Detection and Activation:**

1. WHEN KORAPAY_SECRET_KEY is empty string, THE KoraPay_Service SHALL automatically enable Mock_Mode
2. WHEN KORAPAY_SECRET_KEY length is less than 32 characters, THE KoraPay_Service SHALL automatically enable Mock_Mode
3. WHEN Mock_Mode is enabled, THE KoraPay_Service SHALL log "⚠️  KORAPAY MOCK MODE ACTIVE - No real API calls will be made" at WARNING level during initialization
4. WHEN Mock_Mode is enabled, THE KoraPay_Service SHALL set instance variable self._mock_mode = True
5. THE KoraPay_Service SHALL implement method is_mock_mode() -> bool returning self._mock_mode
6. WHEN Mock_Mode is enabled, THE is_configured() method SHALL return False
7. WHEN Mock_Mode is enabled, THE is_transfer_configured() method SHALL return True (allow UI to show bank details)

**Mock Virtual Account Creation:**

8. THE KoraPay_Service SHALL implement method _mock_create_virtual_account(transaction_reference: str, amount_naira: int, account_name: str, customer_email: str, customer_name: str) -> dict
9. THE Mock_Mode SHALL generate deterministic 10-digit account numbers using formula: str(3000000000 + (sum(ord(c) for c in transaction_reference) % 999999999)).zfill(10)
10. THE Mock_Mode SHALL return bank_name "Wema Bank (Demo)" for all mock accounts
11. THE Mock_Mode SHALL return bank_code "035" (Wema Bank code) for all mock accounts
12. THE Mock_Mode SHALL return account_name matching the provided account_name parameter
13. THE Mock_Mode SHALL return amount matching the provided amount_naira parameter (in Naira, not kobo)
14. THE Mock_Mode SHALL return currency "NGN" for all mock accounts
15. THE Mock_Mode SHALL calculate mock fee as amount * 0.015 (1.5% transaction fee)
16. THE Mock_Mode SHALL calculate mock VAT as fee * 0.075 (7.5% VAT on fee)
17. THE Mock_Mode SHALL return amount_expected as amount + fee + vat when merchant_bears_cost is False
18. THE Mock_Mode SHALL return amount_expected as amount when merchant_bears_cost is True
19. THE Mock_Mode SHALL generate mock payment_reference as f"KPY-CA-MOCK-{transaction_reference[-8:]}"
20. THE Mock_Mode SHALL return status "processing" for newly created mock accounts
21. THE Mock_Mode SHALL return responseCode "Z0" (pending) for backward compatibility
22. THE Mock_Mode SHALL generate expiry_date_in_utc as current UTC time + 30 minutes in ISO format
23. THE Mock_Mode SHALL return complete response dict matching KoraPay structure with nested data.bank_account object
24. THE Mock_Mode SHALL log "[MOCK] Virtual account created | ref={ref} acct={acct} amount=₦{amount} fee=₦{fee}" at WARNING level
25. THE Mock_Mode SHALL return response instantly without network delay

**Mock Transfer Confirmation with Polling Simulation:**

26. THE KoraPay_Service SHALL implement method _mock_confirm_transfer(transaction_reference: str) -> dict
27. THE KoraPay_Service SHALL maintain module-level dict _mock_poll_counts: dict[str, int] = {} for tracking poll attempts
28. THE KoraPay_Service SHALL define module-level constant MOCK_CONFIRM_AFTER = 3 for confirmation threshold
29. WHEN _mock_confirm_transfer is called, THE Mock_Mode SHALL increment _mock_poll_counts[transaction_reference] by 1
30. WHEN poll count is less than MOCK_CONFIRM_AFTER, THE Mock_Mode SHALL return status "processing" and responseCode "Z0"
31. WHEN poll count is less than MOCK_CONFIRM_AFTER, THE Mock_Mode SHALL log "[MOCK] Transfer pending | ref={ref} (poll #{count}/{MOCK_CONFIRM_AFTER})" at WARNING level
32. WHEN poll count equals or exceeds MOCK_CONFIRM_AFTER, THE Mock_Mode SHALL return status "success" and responseCode "00"
33. WHEN poll count equals or exceeds MOCK_CONFIRM_AFTER, THE Mock_Mode SHALL log "[MOCK] Transfer CONFIRMED | ref={ref} (poll #{count})" at WARNING level
34. WHEN poll count equals or exceeds MOCK_CONFIRM_AFTER, THE Mock_Mode SHALL delete transaction_reference from _mock_poll_counts dict (cleanup)
35. THE Mock_Mode SHALL return complete response dict with keys: responseCode, transactionReference, paymentReference, status, amount, currency
36. THE Mock_Mode SHALL generate mock payment_reference as f"KPY-PAY-MOCK-{transaction_reference[-8:]}" for confirmed transfers
37. THE Mock_Mode SHALL include mock transaction_date as current UTC time in format "YYYY-MM-DD HH:MM:SS"
38. THE Mock_Mode SHALL include mock virtual_bank_account_details with payer_bank_account information
39. THE Mock_Mode SHALL generate mock payer_bank_account with bank_name "Test Bank", account_name "Mock Customer", account_number "0000000000"

**Mock Mode Configuration and Control:**

40. THE Mock_Mode SHALL support environment variable KORAPAY_MOCK_CONFIRM_AFTER to override default confirmation threshold
41. WHEN KORAPAY_MOCK_CONFIRM_AFTER is set, THE Mock_Mode SHALL use int(Config.KORAPAY_MOCK_CONFIRM_AFTER) instead of default 3
42. THE Mock_Mode SHALL support environment variable KORAPAY_MOCK_DELAY_MS to simulate network latency
43. WHEN KORAPAY_MOCK_DELAY_MS is set, THE Mock_Mode SHALL sleep for specified milliseconds before returning response
44. THE Mock_Mode SHALL support environment variable KORAPAY_MOCK_FAILURE_RATE to simulate random failures
45. WHEN KORAPAY_MOCK_FAILURE_RATE is set (0.0 to 1.0), THE Mock_Mode SHALL randomly fail requests with specified probability
46. WHEN mock failure is triggered, THE Mock_Mode SHALL raise KoraPayError with message "Mock failure triggered"
47. THE Mock_Mode SHALL log mock configuration at startup: "Mock mode config | confirm_after={n} delay={ms}ms failure_rate={rate}"

**Mock Mode Edge Cases and Error Simulation:**

48. THE Mock_Mode SHALL support special transaction reference prefix "MOCK-FAIL-" to simulate immediate failure
49. WHEN transaction_reference starts with "MOCK-FAIL-", THE Mock_Mode SHALL raise KoraPayError with message "Mock failure: transaction reference contains MOCK-FAIL prefix"
50. THE Mock_Mode SHALL support special transaction reference prefix "MOCK-TIMEOUT-" to simulate timeout
51. WHEN transaction_reference starts with "MOCK-TIMEOUT-", THE Mock_Mode SHALL raise requests.exceptions.Timeout
52. THE Mock_Mode SHALL support special transaction reference prefix "MOCK-400-" to simulate bad request
53. WHEN transaction_reference starts with "MOCK-400-", THE Mock_Mode SHALL raise KoraPayError with message "Mock 400: Bad request"
54. THE Mock_Mode SHALL support special transaction reference prefix "MOCK-401-" to simulate auth failure
55. WHEN transaction_reference starts with "MOCK-401-", THE Mock_Mode SHALL raise KoraPayError with message "Mock 401: Authentication failed"
56. THE Mock_Mode SHALL support special transaction reference prefix "MOCK-429-" to simulate rate limit
57. WHEN transaction_reference starts with "MOCK-429-", THE Mock_Mode SHALL raise KoraPayError with message "Mock 429: Rate limit exceeded"
58. THE Mock_Mode SHALL support special transaction reference prefix "MOCK-500-" to simulate server error
59. WHEN transaction_reference starts with "MOCK-500-", THE Mock_Mode SHALL raise KoraPayError with message "Mock 500: Internal server error"

**Mock Mode Testing Support:**

60. THE Mock_Mode SHALL support method reset_mock_state() to clear _mock_poll_counts for test isolation
61. THE Mock_Mode SHALL support method set_mock_poll_count(reference: str, count: int) for test setup
62. THE Mock_Mode SHALL support method get_mock_poll_count(reference: str) -> int for test assertions
63. THE Mock_Mode SHALL never make actual HTTP requests when Mock_Mode is enabled
64. THE Mock_Mode SHALL never require network connectivity when Mock_Mode is enabled
65. THE Mock_Mode SHALL support testing complete payment flow from link creation to confirmation
66. THE Mock_Mode SHALL support testing polling behavior with multiple status checks
67. THE Mock_Mode SHALL support testing webhook delivery after mock confirmation
68. THE Mock_Mode SHALL support testing email notifications after mock confirmation
69. THE Mock_Mode SHALL support testing QR code generation with mock account details
70. THE Mock_Mode SHALL support testing rate limiting without external API calls
71. THE Mock_Mode SHALL support testing error handling without triggering real API errors
72. THE Mock_Mode SHALL support testing concurrent requests without race conditions
73. THE Mock_Mode SHALL support testing idempotency without duplicate API calls
74. THE Mock_Mode SHALL generate realistic-looking data that passes all validation rules
75. THE Mock_Mode SHALL maintain consistency: same reference always generates same account numberquest amount
52. THE KoraPay_Service SHALL validate response contains field "data.currency" with value "NGN"
53. THE KoraPay_Service SHALL validate response contains field "data.fee" (transaction fee)
54. THE KoraPay_Service SHALL validate response contains field "data.vat" (VAT on fee)
55. THE KoraPay_Service SHALL validate response contains field "data.amount_expected" (amount + fees if customer pays)
56. THE KoraPay_Service SHALL return normalized dict with keys: accountNumber, bankName, accountName, bankCode, expiryDate, amount, transactionReference, paymentReference, responseCode, fee, vat
57. THE KoraPay_Service SHALL map data.bank_account.account_number to accountNumber
58. THE KoraPay_Service SHALL map data.bank_account.bank_name to bankName
59. THE KoraPay_Service SHALL map data.bank_account.account_name to accountName
60. THE KoraPay_Service SHALL map data.bank_account.bank_code to bankCode
61. THE KoraPay_Service SHALL map data.bank_account.expiry_date_in_utc to expiryDate
62. THE KoraPay_Service SHALL map data.reference to transactionReference
63. THE KoraPay_Service SHALL map data.payment_reference to paymentReference
64. THE KoraPay_Service SHALL map data.status "processing" to responseCode "Z0" (pending) for backward compatibility
65. THE KoraPay_Service SHALL map data.status "success" to responseCode "00" (confirmed) for backward compatibility
66. THE KoraPay_Service SHALL map data.status "failed" to responseCode "99" (failed) for backward compatibility
67. THE KoraPay_Service SHALL store data.fee in response dict for fee tracking
68. THE KoraPay_Service SHALL store data.vat in response dict for tax tracking
69. THE KoraPay_Service SHALL log successful creation at INFO level: "Virtual account created | ref={ref} bank={bank} acct={acct} fee={fee}"

**Transfer Confirmation - API Request:**

70. THE KoraPay_Service SHALL implement method confirm_transfer(transaction_reference: str) -> dict
71. THE KoraPay_Service SHALL construct endpoint URL as f"{base_url}/merchant/api/v1/charges/{transaction_reference}"
72. THE KoraPay_Service SHALL use HTTP method GET for transfer confirmation
73. THE KoraPay_Service SHALL use merchant reference (not KoraPay payment_reference) in URL path
74. THE KoraPay_Service SHALL set request headers: Authorization, Accept "application/json"
75. THE KoraPay_Service SHALL set request timeout to (10, 30) for (connect_timeout, read_timeout) in seconds
76. THE KoraPay_Service SHALL set allow_redirects=False to prevent redirect attacks

**Transfer Confirmation - Response Handling:**

77. THE KoraPay_Service SHALL validate response status code is 200 for successful query
78. THE KoraPay_Service SHALL parse response JSON and extract nested "data" object
79. THE KoraPay_Service SHALL validate response contains field "data.status"
80. THE KoraPay_Service SHALL validate response contains field "data.reference"
81. THE KoraPay_Service SHALL validate response contains field "data.amount"
82. THE KoraPay_Service SHALL map data.status "success" to responseCode "00" (confirmed)
83. THE KoraPay_Service SHALL map data.status "processing" to responseCode "Z0" (pending)
84. THE KoraPay_Service SHALL map data.status "failed" to responseCode "99" (failed)
85. THE KoraPay_Service SHALL return normalized dict with keys: responseCode, transactionReference, paymentReference, status, amount
86. THE KoraPay_Service SHALL log status check at INFO level: "Transfer status | ref={ref} code={code} status={status}"

**Error Handling - HTTP Status Codes:**

87. WHEN KoraPay returns HTTP 400, THE KoraPay_Service SHALL parse error response JSON for "message" field
88. WHEN KoraPay returns HTTP 400, THE KoraPay_Service SHALL raise KoraPayError with message "Bad request: {error_message}"
89. WHEN KoraPay returns HTTP 401, THE KoraPay_Service SHALL raise KoraPayError with message "Authentication failed - check KORAPAY_SECRET_KEY"
90. WHEN KoraPay returns HTTP 403, THE KoraPay_Service SHALL raise KoraPayError with message "Access forbidden - check API key permissions"
91. WHEN KoraPay returns HTTP 404, THE KoraPay_Service SHALL raise KoraPayError with message "Transaction not found at KoraPay"
92. WHEN KoraPay returns HTTP 422, THE KoraPay_Service SHALL parse validation errors from response and raise KoraPayError with field-specific messages
93. WHEN KoraPay returns HTTP 429, THE KoraPay_Service SHALL extract Retry-After header value in seconds
94. WHEN KoraPay returns HTTP 429 with Retry-After header, THE KoraPay_Service SHALL wait specified seconds before retry
95. WHEN KoraPay returns HTTP 429 without Retry-After header, THE KoraPay_Service SHALL wait 60 seconds before retry
96. WHEN KoraPay returns HTTP 429, THE KoraPay_Service SHALL retry up to 3 times total
97. WHEN KoraPay returns HTTP 500, THE KoraPay_Service SHALL log "KoraPay internal server error" at ERROR level
98. WHEN KoraPay returns HTTP 500, THE KoraPay_Service SHALL retry with exponential backoff (1s, 2s, 4s)
99. WHEN KoraPay returns HTTP 502, THE KoraPay_Service SHALL log "KoraPay bad gateway" and retry
100. WHEN KoraPay returns HTTP 503, THE KoraPay_Service SHALL log "KoraPay service unavailable" and retry
101. WHEN KoraPay returns HTTP 504, THE KoraPay_Service SHALL log "KoraPay gateway timeout" and retry
102. WHEN all retries exhausted, THE KoraPay_Service SHALL raise KoraPayError with message "KoraPay API unavailable after 3 retries"

**Error Handling - Network and Connection:**

103. WHEN requests.exceptions.Timeout occurs, THE KoraPay_Service SHALL log "KoraPay API timeout after 30s" at ERROR level
104. WHEN requests.exceptions.Timeout occurs, THE KoraPay_Service SHALL retry up to 3 times with exponential backoff
105. WHEN requests.exceptions.ConnectionError occurs, THE KoraPay_Service SHALL log "Cannot connect to KoraPay" at ERROR level
106. WHEN requests.exceptions.ConnectionError occurs, THE KoraPay_Service SHALL retry up to 3 times with exponential backoff
107. WHEN requests.exceptions.SSLError occurs, THE KoraPay_Service SHALL log "SSL certificate verification failed" at ERROR level
108. WHEN requests.exceptions.SSLError occurs, THE KoraPay_Service SHALL raise KoraPayError with message "Payment provider security error"
109. WHEN requests.exceptions.JSONDecodeError occurs, THE KoraPay_Service SHALL log raw response body (truncated to 500 chars) at ERROR level
110. WHEN requests.exceptions.JSONDecodeError occurs, THE KoraPay_Service SHALL raise KoraPayError with message "Invalid JSON response from KoraPay"
111. WHEN socket.gaierror (DNS error) occurs, THE KoraPay_Service SHALL log "DNS resolution failed for KoraPay" at ERROR level
112. WHEN socket.gaierror occurs, THE KoraPay_Service SHALL raise KoraPayError with message "Cannot reach payment provider"

**Response Validation:**

113. THE KoraPay_Service SHALL implement method _validate_response_fields(response_data: dict, required_fields: list) -> None
114. THE KoraPay_Service SHALL check each required field exists in response using nested key notation (e.g., "data.bank_account.account_number")
115. WHEN required field is missing, THE KoraPay_Service SHALL collect all missing fields before raising exception
116. WHEN multiple fields missing, THE KoraPay_Service SHALL raise KoraPayError with message "Missing required fields: {field1}, {field2}, ..."
117. THE KoraPay_Service SHALL validate data types: amount (int/float), reference (str), status (str), account_number (str)
118. WHEN field has wrong type, THE KoraPay_Service SHALL raise KoraPayError with message "Invalid type for {field}: expected {expected}, got {actual}"

**Retry Logic Implementation:**

119. THE KoraPay_Service SHALL implement method _make_request_with_retry(method: str, url: str, **kwargs) -> requests.Response
120. THE KoraPay_Service SHALL define RETRYABLE_EXCEPTIONS = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError)
121. THE KoraPay_Service SHALL define RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)
122. THE KoraPay_Service SHALL implement retry loop: for attempt in range(1, MAX_RETRIES + 1)
123. THE KoraPay_Service SHALL set MAX_RETRIES = 3 as class constant
124. THE KoraPay_Service SHALL calculate retry delay as: delay = 2 ** (attempt - 1) for exponential backoff
125. THE KoraPay_Service SHALL add random jitter: delay += random.uniform(0, 0.5) to prevent thundering herd
126. THE KoraPay_Service SHALL log retry attempts: "Retry attempt {attempt}/{MAX_RETRIES} after {delay}s | ref={ref}"
127. THE KoraPay_Service SHALL NOT retry on 4xx errors except 429 (rate limit)
128. THE KoraPay_Service SHALL extract Retry-After header on 429 and use as delay if present
129. THE KoraPay_Service SHALL raise KoraPayError after all retries exhausted with last error message

**Security Controls:**

130. THE KoraPay_Service SHALL never log KORAPAY_SECRET_KEY in plain text at any log level
131. THE KoraPay_Service SHALL mask API key in logs showing only "sk_****_{last_4_chars}"
132. THE KoraPay_Service SHALL validate KORAPAY_SECRET_KEY starts with "sk_live_" or "sk_test_" before use
133. WHEN KORAPAY_SECRET_KEY has invalid format, THE KoraPay_Service SHALL raise KoraPayError with message "Invalid API key format"
134. THE KoraPay_Service SHALL set verify=True for SSL certificate verification in all requests
135. THE KoraPay_Service SHALL set allow_redirects=False to prevent redirect-based attacks
136. THE KoraPay_Service SHALL validate response Content-Type header is "application/json"
137. WHEN Content-Type is not JSON, THE KoraPay_Service SHALL raise KoraPayError with message "Unexpected response format"
138. THE KoraPay_Service SHALL implement request ID generation using uuid.uuid4() for tracing
139. THE KoraPay_Service SHALL include X-Request-ID header in all API requests
140. THE KoraPay_Service SHALL log request ID in all log messages for correlation

**Performance and Monitoring:**

141. THE KoraPay_Service SHALL measure API request duration using time.perf_counter()
142. THE KoraPay_Service SHALL log request duration in milliseconds: "API request completed | endpoint={endpoint} duration={duration_ms}ms"
143. WHEN request duration exceeds 5000ms, THE KoraPay_Service SHALL log WARNING "Slow KoraPay API response"
144. THE KoraPay_Service SHALL track success/failure counts in instance variables for health monitoring
145. THE KoraPay_Service SHALL implement method get_health_metrics() -> dict returning success_rate, avg_response_time, failures_last_hour
146. THE KoraPay_Service SHALL use collections.deque with maxlen=100 for rolling metrics window
147. THE KoraPay_Service SHALL implement thread-safe metrics updates using threading.Lock
148. THE KoraPay_Service SHALL reset metrics counters every hour using timestamp comparison

**Idempotency and Deduplication:**

149. THE KoraPay_Service SHALL use transaction_reference as idempotency key for all operations
150. WHEN creating virtual account with duplicate reference, THE KoraPay_Service SHALL handle 409 Conflict response
151. WHEN KoraPay returns 409 Conflict, THE KoraPay_Service SHALL query existing transaction and return cached result
152. THE KoraPay_Service SHALL log "Duplicate transaction reference detected, returning cached result" at INFO level
153. THE KoraPay_Service SHALL implement method _get_cached_transaction(reference: str) -> dict for duplicate handling

**Logging and Debugging:**

154. THE KoraPay_Service SHALL log all API requests at INFO level with format: "KoraPay API request | method={method} endpoint={endpoint} ref={ref} request_id={request_id}"
155. THE KoraPay_Service SHALL log all API responses at INFO level with format: "KoraPay API response | status={status} ref={ref} duration={duration}ms request_id={request_id}"
156. THE KoraPay_Service SHALL log request bodies at DEBUG level with sensitive fields masked (customer.email partially masked)
157. THE KoraPay_Service SHALL log response bodies at DEBUG level with full structure for debugging
158. THE KoraPay_Service SHALL never log Authorization header value at any level
159. THE KoraPay_Service SHALL implement structured logging with key=value pairs for easy parsing
160. THE KoraPay_Service SHALL include component="korapay" tag in all log messagespayment after 2 mins if false)
20. THE System SHALL expect response field: `status` (boolean, true for success)
21. THE System SHALL expect response field: `message` (string, e.g., "Bank transfer initiated successfully")
22. THE System SHALL expect response field: `data.currency` (string, "NGN")
23. THE System SHALL expect response field: `data.amount` (number, amount in Naira)
24. THE System SHALL expect response field: `data.amount_expected` (number, amount in Naira)
25. THE System SHALL expect response field: `data.fee` (number, transaction fee in Naira)
26. THE System SHALL expect response field: `data.vat` (number, VAT on fee in Naira)
27. THE System SHALL expect response field: `data.reference` (string, merchant reference)
28. THE System SHALL expect response field: `data.payment_reference` (string, KoraPay reference starting with "KPY-")
29. THE System SHALL expect response field: `data.status` (string, "processing" for new virtual accounts)
30. THE System SHALL expect response field: `data.bank_account.account_name` (string, account name for display)
31. THE System SHALL expect response field: `data.bank_account.account_number` (string, 10-digit virtual account number)
32. THE System SHALL expect response field: `data.bank_account.bank_name` (string, e.g., "wema", "sterling", "providus")
33. THE System SHALL expect response field: `data.bank_account.bank_code` (string, e.g., "035" for Wema)
34. THE System SHALL expect response field: `data.bank_account.expiry_date_in_utc` (string, ISO 8601 timestamp)
35. THE System SHALL expect response field: `data.customer` (object, customer details)
36. THE System SHALL support virtual accounts from Wema Bank, Sterling Bank, and Providus Bank
37. THE System SHALL handle amount in Naira (major currency units), NOT kobo (unlike Quickteller)

#### Acceptance Criteria - Transaction Query API

38. THE System SHALL use endpoint: `GET https://api.korapay.com/merchant/api/v1/charges/{reference}` for querying transaction status
39. THE System SHALL replace `{reference}` with the merchant transaction reference in the URL path
40. THE System SHALL expect the same response structure as the bank transfer creation response
41. THE System SHALL check `data.status` field for transaction status ("processing", "success", "failed")

#### Acceptance Criteria - Webhook Verification

42. THE System SHALL extract webhook signature from header: `x-korapay-signature`
43. THE System SHALL use HMAC SHA256 algorithm for signature verification
44. THE System SHALL sign ONLY the `data` object from webhook payload (NOT the entire payload)
45. THE System SHALL compute signature as: `hmac.new(secret_key.encode(), json.dumps(payload['data']).encode(), hashlib.sha256).hexdigest()`
46. THE System SHALL compare signatures as hex strings (lowercase)
47. THE System SHALL respond with HTTP 200 status code to acknowledge webhook receipt
48. THE System SHALL expect KoraPay to retry webhooks periodically within 72 hours if non-200 response or timeout

#### Acceptance Criteria - Webhook Events

49. THE System SHALL handle webhook event: `charge.success` (payment successful)
50. THE System SHALL handle webhook event: `charge.failed` (payment failed)
51. THE System SHALL handle webhook event: `transfer.success` (payout successful - if applicable)
52. THE System SHALL handle webhook event: `transfer.failed` (payout failed - if applicable)
53. THE System SHALL handle webhook event: `refund.success` (refund successful)
54. THE System SHALL handle webhook event: `refund.failed` (refund failed)

#### Acceptance Criteria - Webhook Payload for Bank Transfer

55. THE System SHALL expect webhook field: `event` (string, e.g., "charge.success")
56. THE System SHALL expect webhook field: `data.fee` (number, fee in Naira)
57. THE System SHALL expect webhook field: `data.amount` (number, amount in Naira)
58. THE System SHALL expect webhook field: `data.status` (string, "success", "failed", "processing")
59. THE System SHALL expect webhook field: `data.currency` (string, "NGN")
60. THE System SHALL expect webhook field: `data.reference` (string, merchant reference)
61. THE System SHALL expect webhook field: `data.transaction_date` (string, format "YYYY-MM-DD HH:MM:SS")
62. THE System SHALL expect webhook field: `data.payment_reference` (string, KoraPay reference "KPY-PAY-xxx")
63. THE System SHALL expect webhook field: `data.virtual_bank_account_details.payer_bank_account.bank_name` (string)
64. THE System SHALL expect webhook field: `data.virtual_bank_account_details.payer_bank_account.account_name` (string)
65. THE System SHALL expect webhook field: `data.virtual_bank_account_details.payer_bank_account.account_number` (string)
66. THE System SHALL expect webhook field: `data.virtual_bank_account_details.virtual_bank_account.bank_name` (string)
67. THE System SHALL expect webhook field: `data.virtual_bank_account_details.virtual_bank_account.permanent` (boolean)
68. THE System SHALL expect webhook field: `data.virtual_bank_account_details.virtual_bank_account.account_name` (string)
69. THE System SHALL expect webhook field: `data.virtual_bank_account_details.virtual_bank_account.account_number` (string)
70. THE System SHALL expect webhook field: `data.virtual_bank_account_details.virtual_bank_account.account_reference` (string, UUID)

#### Acceptance Criteria - Refunds API

71. THE System SHALL use endpoint: `POST https://api.korapay.com/merchant/api/v1/refunds/initiate` for initiating refunds
72. THE System SHALL send refund request with required field: `payment_reference` (string, original KoraPay payment reference)
73. THE System SHALL send refund request with required field: `reference` (string, unique refund reference, max 50 chars)
74. THE System SHALL send refund request with optional field: `amount` (number, partial refund amount - full refund if not specified)
75. THE System SHALL send refund request with optional field: `reason` (string, max 200 chars)
76. THE System SHALL send refund request with optional field: `webhook_url` (string, max 200 chars)
77. THE System SHALL enforce minimum refund amount: NGN 100
78. THE System SHALL handle refund statuses: "processing", "failed", "success"
79. THE System SHALL use endpoint: `GET https://api.korapay.com/merchant/api/v1/refunds/{reference}` for querying refund status
80. THE System SHALL use endpoint: `GET https://api.korapay.com/merchant/api/v1/refunds` for listing refunds
81. THE System SHALL support refund list query params: `currency`, `date_from`, `date_to`, `limit`, `starting_after`, `ending_before`, `status`

#### Acceptance Criteria - Testing/Sandbox

82. THE System SHALL use test API keys (sk_test_*) for sandbox mode
83. THE System SHALL expect sandbox to auto-complete bank transfers after 2 minutes by default
84. THE System SHALL set `auto_complete: false` in sandbox to manually trigger with Sandbox Credit API
85. THE System SHALL use test bank account 033-0000000000 for simulating successful payments in sandbox
86. THE System SHALL use test bank account 035-0000000000 for simulating failed payments in sandbox

#### Acceptance Criteria - Key Differences from Quickteller

87. THE System SHALL use Bearer token authentication (simple) instead of OAuth client credentials flow
88. THE System SHALL send amounts in Naira (1500) instead of Kobo (150000)
89. THE System SHALL NOT implement separate OAuth token endpoint (use secret key directly in Authorization header)
90. THE System SHALL sign ONLY the `data` object for webhook verification (not entire payload like Quickteller)
91. THE System SHALL use the same base URL for test and production (key prefix determines mode, unlike Quickteller's separate URLs)
92. THE System SHALL expect `expiry_date_in_utc` field in virtual account response (not present in Quickteller)
93. THE System SHALL support `metadata` object with max 5 fields (not available in Quickteller)
94. THE System SHALL expect bank names in lowercase format ("wema", "sterling", "providus")

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


### Requirement 26: Implement Currency and Amount Handling

**User Story:** As a developer, I want precise currency and amount handling, so that financial calculations are accurate and prevent rounding errors.

#### Acceptance Criteria

1. THE System SHALL use Python Decimal type for all amount calculations (never float)
2. THE System SHALL use Decimal precision of 12 digits with 2 decimal places for Naira amounts
3. THE System SHALL convert Naira to Kobo by multiplying by 100 and converting to integer
4. THE System SHALL validate that Kobo amounts are integers before sending to KoraPay
5. THE System SHALL validate that Kobo amounts are positive (greater than 0)
6. THE System SHALL validate that Kobo amou

### Requirement 26: Implement Detailed KoraPay API Request/Response Specifications

**User Story:** As a developer, I want exact API specifications for all KoraPay endpoints, so that I can implement requests correctly without ambiguity.

#### Acceptance Criteria

**Virtual Account Creation API - Complete Specification:**

1. THE System SHALL use endpoint POST https://api.korapay.com/merchant/api/v1/charges/bank-transfer for virtual account creation
2. THE System SHALL include request header "Authorization: Bearer {KORAPAY_SECRET_KEY}" with actual secret key value
3. THE System SHALL include request header "Content-Type: application/json"
4. THE System SHALL include request header "Accept: application/json"
5. THE System SHALL include request header "User-Agent: OnePay-KoraPay/1.0"
6. THE System SHALL include request header "X-Request-ID: {uuid4}" for request tracing
7. THE System SHALL construct request body with exact field names: reference, amount, currency, customer, account_name, merchant_bears_cost, narration, notification_url, metadata
8. THE System SHALL set request body field "reference" as string with minimum 8 characters (merchant transaction reference)
9. THE System SHALL set request body field "amount" as number in major currency units (e.g., 1500 for ₦1,500, NOT 150000 kobo)
10. THE System SHALL set request body field "currency" as string "NGN" (Nigerian Naira)
11. THE System SHALL set request body field "customer" as object with required keys "name" and "email"
12. THE System SHALL set request body field "customer.name" as string with customer full name
13. THE System SHALL set request body field "customer.email" as string with valid email format
14. THE System SHALL set request body field "account_name" as string (optional, displayed on bank transfer screen)
15. THE System SHALL set request body field "merchant_bears_cost" as boolean (false = customer pays fees, true = merchant pays fees)
16. THE System SHALL set request body field "narration" as string (optional, max 255 characters, shown on transfer receipt)
17. THE System SHALL set request body field "notification_url" as string (optional, webhook URL for payment notifications)
18. THE System SHALL set request body field "metadata" as object (optional, max 5 fields, field names max 20 chars each)
19. THE System SHALL include metadata field "platform" with value "OnePay"
20. THE System SHALL include metadata field "version" with value "1.0"
21. THE System SHALL include metadata field "user_id" with merchant user ID
22. THE System SHALL set request timeout to (10, 30) tuple for (connect_timeout, read_timeout) in seconds
23. THE System SHALL set allow_redirects=False to prevent redirect attacks
24. THE System SHALL set verify=True for SSL certificate verification

**Virtual Account Creation API - Response Specification:**

25. THE System SHALL expect HTTP status code 200 or 201 for successful virtual account creation
26. THE System SHALL parse response JSON with root-level fields: status, message, data
27. THE System SHALL validate response field "status" is boolean true
28. THE System SHALL validate response field "message" is string "Bank transfer initiated successfully"
29. THE System SHALL extract nested object "data" from response root
30. THE System SHALL validate data contains field "currency" with value "NGN"
31. THE System SHALL validate data contains field "amount" as number matching request amount
32. THE System SHALL validate data contains field "amount_expected" as number (amount + fees if customer pays)
33. THE System SHALL validate data contains field "fee" as number (transaction processing fee)
34. THE System SHALL validate data contains field "vat" as number (VAT on fee, typically 7.5%)
35. THE System SHALL validate data contains field "reference" as string matching request reference
36. THE System SHALL validate data contains field "payment_reference" as string (KoraPay internal ID, format "KPY-CA-*")
37. THE System SHALL validate data contains field "status" with value "processing"
38. THE System SHALL validate data contains nested object "bank_account"
39. THE System SHALL validate data.bank_account contains field "account_name" as string
40. THE System SHALL validate data.bank_account contains field "account_number" as string (10 digits)
41. THE System SHALL validate data.bank_account contains field "bank_name" as string (e.g., "wema", "sterling", "providus")
42. THE System SHALL validate data.bank_account contains field "bank_code" as string (3 digits, e.g., "035")
43. THE System SHALL validate data.bank_account contains field "expiry_date_in_utc" as string in ISO 8601 format
44. THE System SHALL validate data contains nested object "customer" with fields name and email
45. THE System SHALL parse expiry_date_in_utc as datetime using datetime.fromisoformat()
46. THE System SHALL validate expiry_date is in the future (not already expired)
47. THE System SHALL validate account_number is exactly 10 digits
48. THE System SHALL validate bank_code is exactly 3 digits
49. THE System SHALL store all response fields in normalized dict for backward compatibility with existing code

**Transfer Confirmation API - Complete Specification:**

50. THE System SHALL use endpoint GET https://api.korapay.com/merchant/api/v1/charges/{reference} for transfer status query
51. THE System SHALL substitute {reference} with merchant transaction reference (NOT KoraPay payment_reference)
52. THE System SHALL include request header "Authorization: Bearer {KORAPAY_SECRET_KEY}"
53. THE System SHALL include request header "Accept: application/json"
54. THE System SHALL include request header "User-Agent: OnePay-KoraPay/1.0"
55. THE System SHALL include request header "X-Request-ID: {uuid4}"
56. THE System SHALL NOT include request body (GET request)
57. THE System SHALL set request timeout to (10, 30) for (connect_timeout, read_timeout)
58. THE System SHALL set allow_redirects=False
59. THE System SHALL set verify=True for SSL verification

**Transfer Confirmation API - Response Specification:**

60. THE System SHALL expect HTTP status code 200 for successful query
61. THE System SHALL parse response JSON with root-level fields: status, message, data
62. THE System SHALL validate response field "status" is boolean
63. THE System SHALL extract nested object "data" from response root
64. THE System SHALL validate data contains field "status" with values: "success", "processing", "failed"
65. THE System SHALL validate data contains field "reference" matching request reference
66. THE System SHALL validate data contains field "payment_reference" (KoraPay internal ID)
67. THE System SHALL validate data contains field "amount" as number
68. THE System SHALL validate data contains field "currency" with value "NGN"
69. THE System SHALL validate data contains field "fee" as number
70. WHEN data.status is "success", THE System SHALL extract field "transaction_date" in format "YYYY-MM-DD HH:MM:SS"
71. WHEN data.status is "success", THE System SHALL extract nested object "virtual_bank_account_details"
72. WHEN data.status is "success", THE System SHALL extract nested object "virtual_bank_account_details.payer_bank_account"
73. WHEN data.status is "success", THE System SHALL extract payer_bank_account fields: bank_name, account_name, account_number
74. THE System SHALL map data.status "success" to responseCode "00" for backward compatibility
75. THE System SHALL map data.status "processing" to responseCode "Z0" for backward compatibility
76. THE System SHALL map data.status "failed" to responseCode "99" for backward compatibility


### Requirement 27: Implement Detailed KoraPay Webhook Specifications

**User Story:** As a developer, I want exact webhook payload specifications from KoraPay, so that I can parse and validate webhook events correctly.

#### Acceptance Criteria

**Webhook Event Types and Structure:**

1. THE System SHALL support webhook event type "charge.success" for successful bank transfer payments
2. THE System SHALL support webhook event type "charge.failed" for failed payment attempts
3. THE System SHALL support webhook event type "transfer.success" for successful payout transfers (future use)
4. THE System SHALL support webhook event type "transfer.failed" for failed payout transfers (future use)
5. THE System SHALL support webhook event type "refund.success" for successful refund processing
6. THE System SHALL support webhook event type "refund.failed" for failed refund attempts
7. THE System SHALL parse webhook payload with root-level fields: event, data
8. THE System SHALL validate webhook field "event" is string matching one of supported event types
9. THE System SHALL extract nested object "data" containing all transaction details
10. THE System SHALL validate data contains field "fee" as number (transaction fee in Naira)
11. THE System SHALL validate data contains field "amount" as number (transaction amount in Naira)
12. THE System SHALL validate data contains field "status" as string ("success", "failed", "processing")
13. THE System SHALL validate data contains field "currency" as string ("NGN")
14. THE System SHALL validate data contains field "reference" as string (merchant transaction reference)
15. THE System SHALL validate data contains field "payment_reference" as string (KoraPay internal ID, format "KPY-PAY-*")
16. THE System SHALL validate data contains field "transaction_date" as string in format "YYYY-MM-DD HH:MM:SS"
17. THE System SHALL validate data contains nested object "virtual_bank_account_details"
18. THE System SHALL validate virtual_bank_account_details contains nested object "payer_bank_account"
19. THE System SHALL validate payer_bank_account contains field "bank_name" as string
20. THE System SHALL validate payer_bank_account contains field "account_name" as string (customer name)
21. THE System SHALL validate payer_bank_account contains field "account_number" as string (customer account number)
22. THE System SHALL validate virtual_bank_account_details contains nested object "virtual_bank_account"
23. THE System SHALL validate virtual_bank_account contains fields: account_name, account_number, bank_name, bank_code

**Webhook Signature Verification - Exact Algorithm:**

24. THE System SHALL extract signature from HTTP header "x-korapay-signature" (lowercase header name)
25. THE System SHALL extract raw request body as bytes using request.get_data(as_text=False)
26. THE System SHALL parse request body JSON to extract "data" object only
27. THE System SHALL serialize "data" object using json.dumps(data, separators=(',', ':')) for consistent formatting
28. THE System SHALL encode serialized data as UTF-8 bytes
29. THE System SHALL compute HMAC using: hmac.new(KORAPAY_WEBHOOK_SECRET.encode('utf-8'), data_bytes, hashlib.sha256)
30. THE System SHALL extract hexadecimal digest using .hexdigest() method
31. THE System SHALL compare received signature with computed digest using hmac.compare_digest(computed, received)
32. THE System SHALL NOT compare full request body - ONLY the "data" object (KoraPay-specific behavior)
33. THE System SHALL log DEBUG "Webhook signature computation | data_length={len} computed={computed[:16]}... received={received[:16]}..."
34. WHEN signature verification fails, THE System SHALL log the serialized data object (truncated to 200 chars) for debugging
35. WHEN signature verification fails, THE System SHALL NOT log the KORAPAY_WEBHOOK_SECRET value
36. THE System SHALL implement signature verification before any database queries or business logic
37. THE System SHALL return HTTP 401 immediately on signature failure without processing payload
38. THE System SHALL use constant-time comparison to prevent timing attacks revealing valid signatures
39. THE System SHALL validate KORAPAY_WEBHOOK_SECRET is at least 32 characters before computing signature
40. WHEN KORAPAY_WEBHOOK_SECRET is not configured, THE System SHALL return HTTP 500 with error "Webhook secret not configured"

**Webhook Retry and Acknowledgment:**

41. THE System SHALL return HTTP 200 status code within 5 seconds to acknowledge successful webhook receipt
42. WHEN webhook processing takes longer than 5 seconds, THE System SHALL return HTTP 200 immediately and process asynchronously
43. THE System SHALL return JSON response body {"success": true, "tx_ref": "{reference}"} for successful processing
44. THE System SHALL return JSON response body {"success": false, "error": "{message}", "code": "{error_code}"} for failures
45. WHEN webhook returns non-200 status, KoraPay SHALL retry delivery periodically for up to 72 hours
46. THE System SHALL implement idempotency to handle KoraPay retry attempts without duplicate processing
47. THE System SHALL log "Webhook retry detected (idempotent)" when processing already-confirmed transaction
48. THE System SHALL track webhook delivery attempts in transaction.webhook_attempts counter
49. THE System SHALL store last webhook error in transaction.webhook_last_error field (max 500 chars)
50. THE System SHALL update transaction.webhook_delivered_at timestamp on first successful processing


### Requirement 28: Implement Detailed KoraPay Error Code Handling

**User Story:** As a developer, I want comprehensive handling for all KoraPay error codes and scenarios, so that users receive helpful error messages and issues are debuggable.

#### Acceptance Criteria

**HTTP 400 Bad Request - Detailed Handling:**

1. WHEN KoraPay returns HTTP 400, THE System SHALL parse response JSON for error details
2. THE System SHALL extract field "message" from error response as primary error message
3. THE System SHALL extract field "errors" array from response if present (validation errors)
4. WHEN "errors" array exists, THE System SHALL iterate and extract field-specific error messages
5. WHEN "errors" array exists, THE System SHALL format error as "Field {field}: {message}" for each validation error
6. WHEN reference field invalid, THE System SHALL return error "Invalid transaction reference: must be at least 8 characters"
7. WHEN amount field invalid, THE System SHALL return error "Invalid amount: must be between ₦100 and ₦999,999,999"
8. WHEN currency field invalid, THE System SHALL return error "Invalid currency: only NGN supported"
9. WHEN customer.email field invalid, THE System SHALL return error "Invalid customer email format"
10. WHEN customer.name field missing, THE System SHALL return error "Customer name is required"
11. THE System SHALL log ERROR "KoraPay 400 error | ref={ref} errors={errors_json}"
12. THE System SHALL raise KoraPayError with concatenated error messages from all validation errors

**HTTP 401 Unauthorized - Authentication Failure:**

13. WHEN KoraPay returns HTTP 401, THE System SHALL log ERROR "KoraPay authentication failed | key_prefix={key[:7]}"
14. WHEN KoraPay returns HTTP 401, THE System SHALL check if KORAPAY_SECRET_KEY starts with "sk_live_" or "sk_test_"
15. WHEN key format invalid, THE System SHALL raise KoraPayError with message "Invalid API key format - must start with sk_live_ or sk_test_"
16. WHEN key format valid, THE System SHALL raise KoraPayError with message "Authentication failed - check API key is active in KoraPay dashboard"
17. THE System SHALL log audit event "korapay.auth_failed" with timestamp and masked key
18. THE System SHALL NOT retry 401 errors (authentication won't succeed on retry)
19. THE System SHALL suggest checking KoraPay dashboard API settings in error message
20. THE System SHALL suggest verifying environment (production vs sandbox) matches API key type

**HTTP 403 Forbidden - Permission Denied:**

21. WHEN KoraPay returns HTTP 403, THE System SHALL parse response for "message" field
22. WHEN KoraPay returns HTTP 403, THE System SHALL log ERROR "KoraPay access forbidden | ref={ref} message={message}"
23. THE System SHALL raise KoraPayError with message "Access denied - API key may lack required permissions"
24. THE System SHALL suggest checking API key permissions in KoraPay dashboard
25. THE System SHALL NOT retry 403 errors (permissions won't change on retry)

**HTTP 404 Not Found - Transaction Not Found:**

26. WHEN KoraPay returns HTTP 404, THE System SHALL log WARNING "Transaction not found at KoraPay | ref={ref}"
27. WHEN KoraPay returns HTTP 404, THE System SHALL raise KoraPayError with message "Transaction not found at payment provider"
28. THE System SHALL distinguish between "never created" vs "expired and deleted" scenarios
29. WHEN transaction exists locally but not at KoraPay, THE System SHALL log ERROR "Data inconsistency detected"
30. THE System SHALL NOT retry 404 errors (transaction won't appear on retry)

**HTTP 422 Unprocessable Entity - Validation Errors:**

31. WHEN KoraPay returns HTTP 422, THE System SHALL parse response JSON for "errors" array
32. THE System SHALL extract validation errors with fields: field, message, code
33. THE System SHALL format each validation error as "{field}: {message} (code: {code})"
34. THE System SHALL concatenate all validation errors with newline separator
35. THE System SHALL raise KoraPayError with message "Validation failed:\n{errors}"
36. THE System SHALL log ERROR "KoraPay validation errors | ref={ref} errors={errors_json}"
37. THE System SHALL NOT retry 422 errors (validation won't pass on retry)

**HTTP 429 Rate Limit - Detailed Handling:**

38. WHEN KoraPay returns HTTP 429, THE System SHALL extract "Retry-After" header value
39. WHEN Retry-After header present, THE System SHALL parse value as integer seconds
40. WHEN Retry-After header present, THE System SHALL wait specified seconds before retry
41. WHEN Retry-After header missing, THE System SHALL wait 60 seconds before retry
42. THE System SHALL log WARNING "KoraPay rate limit exceeded | ref={ref} retry_after={seconds}s"
43. THE System SHALL retry 429 errors up to 3 times total
44. WHEN all retries exhausted, THE System SHALL raise KoraPayError with message "Rate limit exceeded - please try again later"
45. THE System SHALL track rate limit occurrences in metrics for monitoring
46. WHEN rate limits occur frequently (>5 per hour), THE System SHALL log CRITICAL alert
47. THE System SHALL include rate limit guidance in error message: "Reduce request frequency or contact KoraPay support"

**HTTP 500/502/503/504 Server Errors - Retry Logic:**

48. WHEN KoraPay returns HTTP 500, THE System SHALL log ERROR "KoraPay internal server error | ref={ref} status=500"
49. WHEN KoraPay returns HTTP 502, THE System SHALL log ERROR "KoraPay bad gateway | ref={ref} status=502"
50. WHEN KoraPay returns HTTP 503, THE System SHALL log ERROR "KoraPay service unavailable | ref={ref} status=503"
51. WHEN KoraPay returns HTTP 504, THE System SHALL log ERROR "KoraPay gateway timeout | ref={ref} status=504"
52. THE System SHALL retry 5xx errors with exponential backoff: 1 second, 2 seconds, 4 seconds
53. THE System SHALL add random jitter 0-500ms to each retry delay to prevent thundering herd
54. THE System SHALL log "Retry attempt {n}/3 after {delay}s | ref={ref} last_error={status}" before each retry
55. WHEN all 3 retries fail, THE System SHALL raise KoraPayError with message "Payment provider temporarily unavailable (HTTP {status})"
56. THE System SHALL track 5xx error frequency in metrics
57. WHEN 5xx errors exceed 10 per hour, THE System SHALL log CRITICAL "KoraPay experiencing high error rate"
58. THE System SHALL include incident ID from KoraPay response in error logs if present

**Network and Connection Errors:**

59. WHEN requests.exceptions.Timeout occurs, THE System SHALL log ERROR "KoraPay API timeout | ref={ref} timeout=30s endpoint={endpoint}"
60. WHEN requests.exceptions.ConnectionError occurs, THE System SHALL log ERROR "Cannot connect to KoraPay | ref={ref} error={error}"
61. WHEN requests.exceptions.SSLError occurs, THE System SHALL log ERROR "SSL verification failed | ref={ref} error={error}"
62. WHEN socket.gaierror occurs, THE System SHALL log ERROR "DNS resolution failed | ref={ref} hostname={hostname}"
63. THE System SHALL retry Timeout errors up to 3 times with exponential backoff
64. THE System SHALL retry ConnectionError up to 3 times with exponential backoff
65. THE System SHALL NOT retry SSLError (indicates security issue, not transient failure)
66. THE System SHALL NOT retry DNS errors (indicates configuration issue)
67. WHEN SSLError occurs, THE System SHALL raise KoraPayError with message "Payment provider security error - SSL certificate invalid"
68. WHEN DNS error occurs, THE System SHALL raise KoraPayError with message "Cannot reach payment provider - check network configuration"
69. THE System SHALL include original exception details in KoraPayError for debugging
70. THE System SHALL log full exception stack trace at DEBUG level for all network errors


### Requirement 29: Implement KoraPay Refund API Integration

**User Story:** As a merchant, I want to initiate refunds through KoraPay API with complete error handling, so that I can return payments to customers reliably.

#### Acceptance Criteria

**Refund API - Request Specification:**

1. THE System SHALL implement method initiate_refund(payment_reference: str, refund_reference: str, amount: Decimal = None, reason: str = None) -> dict in KoraPay_Service
2. THE System SHALL use endpoint POST https://api.korapay.com/merchant/api/v1/refunds/initiate for refund initiation
3. THE System SHALL include request header "Authorization: Bearer {KORAPAY_SECRET_KEY}"
4. THE System SHALL include request header "Content-Type: application/json"
5. THE System SHALL include request header "Accept: application/json"
6. THE System SHALL include request header "User-Agent: OnePay-KoraPay/1.0"
7. THE System SHALL include request header "X-Request-ID: {uuid4}"
8. THE System SHALL construct request body with fields: payment_reference, reference, amount, reason, webhook_url
9. THE System SHALL set body field "payment_reference" to merchant transaction reference (NOT KoraPay payment_reference)
10. THE System SHALL set body field "reference" to unique refund reference (max 50 characters, merchant-generated)
11. THE System SHALL generate refund_reference as f"REFUND-{tx_ref}-{timestamp}" if not provided
12. THE System SHALL set body field "amount" as number in Naira (optional, full amount if omitted)
13. THE System SHALL validate refund amount is at least ₦100 (KoraPay minimum)
14. THE System SHALL validate refund amount does not exceed original transaction amount
15. THE System SHALL set body field "reason" as string (optional, max 200 characters)
16. THE System SHALL set body field "webhook_url" as string (optional, max 200 characters, HTTPS only)
17. THE System SHALL validate webhook_url using validate_webhook_url() function
18. THE System SHALL set request timeout to (10, 30) for (connect_timeout, read_timeout)

**Refund API - Response Specification:**

19. THE System SHALL expect HTTP status code 200 or 201 for successful refund initiation
20. THE System SHALL parse response JSON with root-level fields: status, message, data
21. THE System SHALL validate response field "status" is boolean true
22. THE System SHALL extract nested object "data" from response
23. THE System SHALL validate data contains field "reference" matching request refund reference
24. THE System SHALL validate data contains field "payment_reference" matching request payment reference
25. THE System SHALL validate data contains field "amount" as number (refund amount in Naira)
26. THE System SHALL validate data contains field "status" with values: "processing", "success", "failed"
27. THE System SHALL validate data contains field "currency" with value "NGN"
28. THE System SHALL store refund details in new database table refunds with fields: id, transaction_id, refund_reference, amount, status, reason, created_at, processed_at
29. THE System SHALL create foreign key relationship refunds.transaction_id -> transactions.id with ON DELETE CASCADE
30. THE System SHALL update transaction.status to new enum value REFUNDED when refund succeeds
31. THE System SHALL log audit event "payment.refund_initiated" with user_id, tx_ref, refund_reference, amount, reason

**Refund Query API - Specification:**

32. THE System SHALL implement method query_refund(refund_reference: str) -> dict in KoraPay_Service
33. THE System SHALL use endpoint GET https://api.korapay.com/merchant/api/v1/refunds/{refund_reference} for refund status query
34. THE System SHALL substitute {refund_reference} with merchant refund reference
35. THE System SHALL include standard headers: Authorization, Accept, User-Agent, X-Request-ID
36. THE System SHALL parse response with fields: status, message, data
37. THE System SHALL validate data contains fields: reference, payment_reference, amount, status, currency, created_at, processed_at
38. THE System SHALL update local refund record status based on data.status value
39. WHEN data.status is "success", THE System SHALL update refund.processed_at timestamp
40. WHEN data.status is "failed", THE System SHALL store failure reason in refund.failure_reason field
41. THE System SHALL log audit event "payment.refund_completed" when status changes to success
42. THE System SHALL send merchant email notification when refund completes
43. THE System SHALL send customer email notification when refund completes

**Refund List API - Specification:**

44. THE System SHALL implement method list_refunds(currency: str = "NGN", date_from: str = None, date_to: str = None, status: str = None, limit: int = 50) -> dict
45. THE System SHALL use endpoint GET https://api.korapay.com/merchant/api/v1/refunds with query parameters
46. THE System SHALL include query parameter "currency" with value from parameter
47. THE System SHALL include query parameter "date_from" in format YYYY-MM-DD when provided
48. THE System SHALL include query parameter "date_to" in format YYYY-MM-DD when provided
49. THE System SHALL include query parameter "status" with values: processing, success, failed when provided
50. THE System SHALL include query parameter "limit" with integer value (default 50, max 100)
51. THE System SHALL parse response with fields: status, message, data (array), pagination
52. THE System SHALL validate data is array of refund objects
53. THE System SHALL extract pagination fields: next_cursor, prev_cursor, has_more
54. THE System SHALL implement cursor-based pagination using next_cursor for subsequent requests
55. THE System SHALL reconcile KoraPay refund list with local refunds table
56. WHEN refund exists at KoraPay but not locally, THE System SHALL log WARNING "Orphaned refund detected | refund_ref={ref}"
57. WHEN refund status differs between KoraPay and local DB, THE System SHALL log WARNING "Refund status mismatch | ref={ref} korapay={kp_status} local={local_status}"


### Requirement 30: Implement Database Schema Extensions for KoraPay

**User Story:** As a database administrator, I want schema extensions to store KoraPay-specific data, so that all payment provider information is preserved for reconciliation and auditing.

#### Acceptance Criteria

**Transaction Table Extensions:**

1. THE System SHALL add column payment_provider_reference VARCHAR(100) to transactions table for storing KoraPay payment_reference
2. THE System SHALL add column provider_fee NUMERIC(12,2) to transactions table for storing KoraPay transaction fee
3. THE System SHALL add column provider_vat NUMERIC(12,2) to transactions table for storing VAT on fee
4. THE System SHALL add column provider_transaction_date DATETIME to transactions table for storing KoraPay transaction timestamp
5. THE System SHALL add column payer_bank_details TEXT to transactions table for storing JSON of payer bank account info
6. THE System SHALL add column failure_reason VARCHAR(500) to transactions table for storing payment failure reasons
7. THE System SHALL add column provider_status VARCHAR(50) to transactions table for storing raw KoraPay status value
8. THE System SHALL add column bank_code VARCHAR(10) to transactions table for storing 3-digit bank code
9. THE System SHALL add column virtual_account_expiry DATETIME to transactions table for storing account expiry timestamp
10. THE System SHALL add index idx_payment_provider_reference ON transactions(payment_provider_reference) for fast lookups
11. THE System SHALL add index idx_provider_transaction_date ON transactions(provider_transaction_date) for date range queries
12. THE System SHALL make all new columns nullable to support existing records
13. THE System SHALL create Alembic migration script with upgrade() and downgrade() functions
14. THE System SHALL test migration on copy of production database before deployment
15. THE System SHALL document migration in alembic/versions/YYYYMMDDHHMMSS_add_korapay_fields.py

**Refunds Table Creation:**

16. THE System SHALL create new table refunds with columns: id, transaction_id, refund_reference, amount, currency, status, reason, created_at, processed_at, failure_reason, provider_refund_id
17. THE System SHALL set refunds.id as INTEGER PRIMARY KEY AUTOINCREMENT
18. THE System SHALL set refunds.transaction_id as INTEGER with FOREIGN KEY to transactions.id ON DELETE CASCADE
19. THE System SHALL set refunds.refund_reference as VARCHAR(100) UNIQUE NOT NULL with index
20. THE System SHALL set refunds.amount as NUMERIC(12,2) NOT NULL
21. THE System SHALL set refunds.currency as VARCHAR(10) DEFAULT 'NGN'
22. THE System SHALL set refunds.status as VARCHAR(50) NOT NULL with values: processing, success, failed
23. THE System SHALL set refunds.reason as VARCHAR(500) nullable
24. THE System SHALL set refunds.created_at as DATETIME NOT NULL with default current UTC timestamp
25. THE System SHALL set refunds.processed_at as DATETIME nullable
26. THE System SHALL set refunds.failure_reason as VARCHAR(500) nullable
27. THE System SHALL set refunds.provider_refund_id as VARCHAR(100) nullable for KoraPay internal refund ID
28. THE System SHALL add index idx_refunds_transaction_id ON refunds(transaction_id)
29. THE System SHALL add index idx_refunds_status ON refunds(status)
30. THE System SHALL add index idx_refunds_created_at ON refunds(created_at)


### Requirement 31: Implement Detailed Configuration Management with Validation

**User Story:** As a system administrator, I want comprehensive configuration management with validation, so that misconfigurations are caught at startup before causing runtime errors.

#### Acceptance Criteria

**Configuration Variables - Complete Specification:**

1. THE Configuration_Service SHALL add KORAPAY_SECRET_KEY to BaseConfig class in config.py
2. THE Configuration_Service SHALL load KORAPAY_SECRET_KEY from os.getenv("KORAPAY_SECRET_KEY", "")
3. THE Configuration_Service SHALL add KORAPAY_WEBHOOK_SECRET to BaseConfig class
4. THE Configuration_Service SHALL load KORAPAY_WEBHOOK_SECRET from os.getenv("KORAPAY_WEBHOOK_SECRET", "")
5. THE Configuration_Service SHALL add KORAPAY_BASE_URL to BaseConfig class with default "https://api.korapay.com"
6. THE Configuration_Service SHALL add KORAPAY_USE_SANDBOX to BaseConfig class as boolean
7. THE Configuration_Service SHALL load KORAPAY_USE_SANDBOX from os.getenv("KORAPAY_USE_SANDBOX", "false").lower() == "true"
8. THE Configuration_Service SHALL add KORAPAY_WEBHOOK_URL to BaseConfig class for webhook endpoint
9. THE Configuration_Service SHALL load KORAPAY_WEBHOOK_URL from os.getenv("KORAPAY_WEBHOOK_URL", "")
10. THE Configuration_Service SHALL add KORAPAY_TIMEOUT_SECONDS to BaseConfig with default 30
11. THE Configuration_Service SHALL add KORAPAY_CONNECT_TIMEOUT_SECONDS to BaseConfig with default 10
12. THE Configuration_Service SHALL add KORAPAY_MAX_RETRIES to BaseConfig with default 3
13. THE Configuration_Service SHALL add KORAPAY_MOCK_CONFIRM_AFTER to BaseConfig with default 3
14. THE Configuration_Service SHALL add KORAPAY_MOCK_DELAY_MS to BaseConfig with default 0
15. THE Configuration_Service SHALL add KORAPAY_MOCK_FAILURE_RATE to BaseConfig with default 0.0

**Configuration Validation - Production Environment:**

16. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_SECRET_KEY is not empty
17. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_SECRET_KEY length >= 32 characters
18. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_SECRET_KEY starts with "sk_live_"
19. WHERE APP_ENV is "production" AND KORAPAY_SECRET_KEY starts with "sk_test_", THE Configuration_Service SHALL abort with error "Cannot use test API key in production"
20. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_WEBHOOK_SECRET is not empty
21. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_WEBHOOK_SECRET length >= 32 characters
22. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_SECRET_KEY != KORAPAY_WEBHOOK_SECRET
23. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_WEBHOOK_SECRET != HMAC_SECRET
24. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_WEBHOOK_SECRET != WEBHOOK_SECRET
25. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_USE_SANDBOX is False
26. WHERE APP_ENV is "production" AND KORAPAY_USE_SANDBOX is True, THE Configuration_Service SHALL abort with error "Cannot use sandbox mode in production"
27. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_WEBHOOK_URL starts with "https://"
28. WHERE APP_ENV is "production", THE Configuration_Service SHALL validate KORAPAY_WEBHOOK_URL is publicly accessible (not localhost/private IP)
29. WHERE APP_ENV is "production" AND any validation fails, THE Configuration_Service SHALL call sys.exit(1) to abort startup
30. WHERE APP_ENV is "production" AND any validation fails, THE Configuration_Service SHALL log CRITICAL with all validation errors listed

**Configuration Validation - Development/Testing Environments:**

31. WHERE APP_ENV is "development", THE Configuration_Service SHALL allow empty KORAPAY_SECRET_KEY (enables mock mode)
32. WHERE APP_ENV is "development", THE Configuration_Service SHALL allow KORAPAY_SECRET_KEY starting with "sk_test_"
33. WHERE APP_ENV is "development", THE Configuration_Service SHALL allow KORAPAY_USE_SANDBOX = True
34. WHERE APP_ENV is "testing", THE Configuration_Service SHALL use fixed test values for deterministic tests
35. WHERE APP_ENV is "testing", THE Configuration_Service SHALL set KORAPAY_SECRET_KEY = "sk_test_test_key_for_unit_tests_only_32chars"
36. WHERE APP_ENV is "testing", THE Configuration_Service SHALL set KORAPAY_WEBHOOK_SECRET = "test_webhook_secret_32_characters"
37. WHERE APP_ENV is "testing", THE Configuration_Service SHALL set KORAPAY_USE_SANDBOX = True
38. WHERE APP_ENV is "testing", THE Configuration_Service SHALL set KORAPAY_MOCK_CONFIRM_AFTER = 1 for fast tests

**Configuration Documentation in .env.example:**

39. THE Configuration_Service SHALL add section "# ── KoraPay Payment Gateway ──" to .env.example
40. THE Configuration_Service SHALL document KORAPAY_SECRET_KEY with comment "# Get from: https://korapay.com/dashboard -> Settings -> API Configuration"
41. THE Configuration_Service SHALL document KORAPAY_SECRET_KEY with comment "# Production: sk_live_*** | Sandbox: sk_test_***"
42. THE Configuration_Service SHALL document KORAPAY_SECRET_KEY with example "KORAPAY_SECRET_KEY=sk_live_your_secret_key_here"
43. THE Configuration_Service SHALL document KORAPAY_WEBHOOK_SECRET with comment "# Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
44. THE Configuration_Service SHALL document KORAPAY_WEBHOOK_SECRET with comment "# MUST be different from KORAPAY_SECRET_KEY and other secrets"
45. THE Configuration_Service SHALL document KORAPAY_USE_SANDBOX with comment "# Set to true for testing, false for production"
46. THE Configuration_Service SHALL document KORAPAY_WEBHOOK_URL with comment "# Your public webhook endpoint (e.g., https://yourdomain.com/api/webhooks/korapay)"
47. THE Configuration_Service SHALL document KORAPAY_WEBHOOK_URL with comment "# Configure this URL in KoraPay dashboard -> Settings -> Webhooks"
48. THE Configuration_Service SHALL add comment "# Optional: Mock mode configuration (development only)"
49. THE Configuration_Service SHALL document KORAPAY_MOCK_CONFIRM_AFTER with comment "# Number of polls before mock confirmation (default: 3)"
50. THE Configuration_Service SHALL document KORAPAY_MOCK_DELAY_MS with comment "# Simulated network latency in milliseconds (default: 0)"

**Configuration Validation Error Messages:**

51. WHEN KORAPAY_SECRET_KEY is empty in production, THE Configuration_Service SHALL log "KORAPAY_SECRET_KEY is required in production environment"
52. WHEN KORAPAY_SECRET_KEY too short, THE Configuration_Service SHALL log "KORAPAY_SECRET_KEY must be at least 32 characters (current: {length})"
53. WHEN KORAPAY_SECRET_KEY has wrong prefix, THE Configuration_Service SHALL log "KORAPAY_SECRET_KEY must start with sk_live_ in production (current: {prefix})"
54. WHEN secrets are not unique, THE Configuration_Service SHALL log "KORAPAY_SECRET_KEY and KORAPAY_WEBHOOK_SECRET must be different values"
55. WHEN sandbox mode in production, THE Configuration_Service SHALL log "KORAPAY_USE_SANDBOX must be false in production environment"
56. THE Configuration_Service SHALL provide actionable guidance in all error messages
57. THE Configuration_Service SHALL include command to generate secrets in error messages
58. THE Configuration_Service SHALL include link to KoraPay dashboard in error messages


### Requirement 32: Implement Comprehensive Amount and Currency Handling

**User Story:** As a developer, I want precise amount handling that prevents rounding errors and correctly converts between Naira and kobo, so that financial calculations are accurate.

#### Acceptance Criteria

**Amount Conversion - Naira to Kobo (Legacy Compatibility):**

1. THE System SHALL maintain internal amounts in Decimal type with precision (12, 2)
2. THE System SHALL store amounts in database as NUMERIC(12, 2) representing Naira
3. WHEN converting for display, THE System SHALL multiply Decimal amount by 100 to get kobo as integer
4. WHEN converting from kobo input, THE System SHALL divide by 100 and convert to Decimal
5. THE System SHALL use Decimal("0.01") as quantum for rounding to 2 decimal places
6. THE System SHALL use ROUND_HALF_UP rounding mode for all financial calculations
7. THE System SHALL validate kobo amounts are integers before any operations
8. THE System SHALL validate kobo amounts are positive (> 0)
9. THE System SHALL validate kobo amounts do not exceed 99999999999999 (max 14 digits)

**Amount Conversion - Naira for KoraPay (Major Currency Units):**

10. THE System SHALL send amounts to KoraPay API in major currency units (Naira, not kobo)
11. THE System SHALL convert Decimal amount to integer Naira by: int(amount) when amount has no decimal places
12. THE System SHALL convert Decimal amount to float Naira by: float(amount) when amount has decimal places
13. THE System SHALL validate KoraPay amount is between 100 and 999999999 (₦100 to ₦999,999,999)
14. THE System SHALL log WARNING when amount has fractional Naira (e.g., ₦1500.50) as KoraPay may round
15. THE System SHALL round fractional amounts to 2 decimal places before sending to KoraPay
16. WHEN KoraPay response amount differs from request amount, THE System SHALL log ERROR "Amount mismatch"
17. THE System SHALL validate response amount matches request amount within 0.01 tolerance (1 kobo)

**Currency Validation:**

18. THE System SHALL validate currency field is exactly "NGN" before sending to KoraPay
19. THE System SHALL reject transactions with currency other than "NGN" with error "Only NGN currency supported"
20. THE System SHALL validate KoraPay response currency is "NGN"
21. WHEN response currency is not "NGN", THE System SHALL raise KoraPayError with message "Unexpected currency in response"
22. THE System SHALL store currency as VARCHAR(10) in database for future multi-currency support
23. THE System SHALL use ISO 4217 alpha code "NGN" (not numeric code 566)

**Fee Calculation and Storage:**

24. THE System SHALL extract fee from KoraPay response data.fee field
25. THE System SHALL extract VAT from KoraPay response data.vat field
26. THE System SHALL calculate total_cost as amount + fee + vat when merchant_bears_cost is False
27. THE System SHALL calculate total_cost as amount when merchant_bears_cost is True
28. THE System SHALL store fee in transaction.provider_fee as Decimal
29. THE System SHALL store VAT in transaction.provider_vat as Decimal
30. THE System SHALL display fee breakdown to merchant in transaction history
31. THE System SHALL include fee in CSV export with column "Provider Fee"
32. THE System SHALL include VAT in CSV export with column "Provider VAT"
33. THE System SHALL calculate merchant net amount as amount - fee - vat for accounting
34. THE System SHALL validate fee is non-negative
35. THE System SHALL validate VAT is non-negative
36. THE System SHALL validate fee + vat does not exceed amount (sanity check)


### Requirement 33: Implement Detailed Migration Procedure with Rollback Plan

**User Story:** As a DevOps engineer, I want a detailed step-by-step migration procedure with rollback plan, so that I can safely migrate from Quickteller to KoraPay with minimal risk.

#### Acceptance Criteria

**Pre-Migration Preparation:**

1. THE System SHALL create migration script scripts/migrate_to_korapay.py with phases: validate, backup, migrate, verify
2. THE Migration_Script SHALL implement phase 1: validate_current_state() checking all Quickteller transactions are complete
3. THE Migration_Script SHALL query transactions with status PENDING and count them
4. WHEN pending transactions exist, THE Migration_Script SHALL abort with error "Cannot migrate with {count} pending transactions - wait for completion or expire them"
5. THE Migration_Script SHALL validate all transactions have virtual_account_number populated
6. THE Migration_Script SHALL compute SHA256 checksum of all transaction records (id, tx_ref, amount, status, virtual_account_number)
7. THE Migration_Script SHALL export checksum to file migration_checksum_pre.txt with timestamp
8. THE Migration_Script SHALL count total transactions and export to migration_stats_pre.json
9. THE Migration_Script SHALL validate database schema version matches expected version
10. THE Migration_Script SHALL validate no Alembic migrations are pending
11. THE Migration_Script SHALL test database connectivity and write permissions
12. THE Migration_Script SHALL validate sufficient disk space for backup (at least 2x database size)

**Backup Creation:**

13. THE Migration_Script SHALL implement phase 2: create_backup() creating full database backup
14. THE Migration_Script SHALL generate backup filename as onepay_backup_YYYYMMDD_HHMMSS.db for SQLite
15. THE Migration_Script SHALL use pg_dump for PostgreSQL with format: pg_dump -Fc onepay > backup.dump
16. THE Migration_Script SHALL verify backup file exists and size > 0 after creation
17. THE Migration_Script SHALL compute SHA256 checksum of backup file
18. THE Migration_Script SHALL test backup integrity by restoring to temporary database
19. THE Migration_Script SHALL query transaction count from restored backup and compare with original
20. WHEN backup verification fails, THE Migration_Script SHALL abort with error "Backup verification failed"
21. THE Migration_Script SHALL export backup metadata to migration_backup_info.json with: filename, size, checksum, timestamp, transaction_count
22. THE Migration_Script SHALL log "Backup created and verified | file={filename} size={size_mb}MB transactions={count}"

**Code Migration:**

23. THE Migration_Script SHALL implement phase 3: migrate_code() performing code changes
24. THE Migration_Script SHALL create git branch "migration/korapay-integration" before changes
25. THE Migration_Script SHALL delete file services/quickteller.py
26. THE Migration_Script SHALL create file services/korapay.py with complete KoraPay implementation
27. THE Migration_Script SHALL update blueprints/payments.py replacing "from services.quickteller import quickteller" with "from services.korapay import korapay"
28. THE Migration_Script SHALL update blueprints/public.py replacing quickteller references with korapay
29. THE Migration_Script SHALL update config.py removing Quickteller variables and adding KoraPay variables
30. THE Migration_Script SHALL update .env.example removing Quickteller section and adding KoraPay section
31. THE Migration_Script SHALL run git diff to show all changes
32. THE Migration_Script SHALL prompt user to review changes before committing
33. THE Migration_Script SHALL commit changes with message "feat: migrate from Quickteller to KoraPay integration"
34. THE Migration_Script SHALL create git tag "pre-korapay-migration" at previous commit for easy rollback

**Post-Migration Verification:**

35. THE Migration_Script SHALL implement phase 4: verify_migration() validating migration success
36. THE Migration_Script SHALL query transaction count and compare with pre-migration count
37. WHEN transaction counts differ, THE Migration_Script SHALL abort with error "Transaction count mismatch"
38. THE Migration_Script SHALL compute SHA256 checksum of all transaction records post-migration
39. WHEN checksums differ, THE Migration_Script SHALL abort with error "Data integrity check failed"
40. THE Migration_Script SHALL query all transactions and validate foreign key relationships intact
41. THE Migration_Script SHALL validate all virtual_account_number values still present
42. THE Migration_Script SHALL validate all webhook_url values still present
43. THE Migration_Script SHALL validate all audit_log entries still present
44. THE Migration_Script SHALL test KoraPay service initialization with is_configured()
45. THE Migration_Script SHALL test mock mode by creating test virtual account
46. THE Migration_Script SHALL test health check endpoint returns korapay status
47. THE Migration_Script SHALL export verification report to migration_verification_report.txt
48. THE Migration_Script SHALL log "Migration verification complete | status=SUCCESS transactions={count} integrity=OK"

**Rollback Procedure:**

49. THE System SHALL create rollback script scripts/rollback_to_quickteller.py
50. THE Rollback_Script SHALL implement phase 1: stop_application() gracefully stopping Flask app
51. THE Rollback_Script SHALL implement phase 2: restore_backup() restoring database from backup file
52. THE Rollback_Script SHALL validate backup file exists before attempting restore
53. THE Rollback_Script SHALL restore SQLite using: cp backup.db onepay.db
54. THE Rollback_Script SHALL restore PostgreSQL using: pg_restore -d onepay backup.dump
55. THE Rollback_Script SHALL verify restored database transaction count matches backup metadata
56. THE Rollback_Script SHALL implement phase 3: revert_code() using git to revert code changes
57. THE Rollback_Script SHALL execute: git checkout pre-korapay-migration to revert to tagged commit
58. THE Rollback_Script SHALL verify services/quickteller.py exists after revert
59. THE Rollback_Script SHALL verify services/korapay.py does not exist after revert
60. THE Rollback_Script SHALL implement phase 4: verify_rollback() testing Quickteller functionality
61. THE Rollback_Script SHALL test Quickteller service initialization
62. THE Rollback_Script SHALL test mock mode virtual account creation with Quickteller
63. THE Rollback_Script SHALL test health check endpoint returns quickteller status
64. THE Rollback_Script SHALL log "Rollback complete | database=restored code=reverted status=OPERATIONAL"
65. THE Rollback_Script SHALL document rollback decision criteria: "Rollback if migration verification fails OR critical issues within 24 hours"
66. THE Rollback_Script SHALL document rollback time estimate: "15-30 minutes downtime"
67. THE Rollback_Script SHALL include rollback testing procedure for staging environment
68. THE Rollback_Script SHALL document post-rollback communication plan for merchants


### Requirement 34: Implement Detailed Testing Strategy with Edge Cases

**User Story:** As a QA engineer, I want comprehensive test coverage including edge cases and error scenarios, so that the KoraPay integration is reliable in production.

#### Acceptance Criteria

**Unit Test Coverage - KoraPay Service:**

1. THE Test_Suite SHALL create file tests/unit/test_korapay_service.py
2. THE Test_Suite SHALL achieve minimum 95% code coverage for services/korapay.py
3. THE Test_Suite SHALL use pytest framework with fixtures for test setup
4. THE Test_Suite SHALL use unittest.mock.patch to mock requests.Session.post and requests.Session.get
5. THE Test_Suite SHALL use responses library as alternative mocking approach for HTTP requests
6. THE Test_Suite SHALL create fixture mock_korapay_config() setting test configuration values
7. THE Test_Suite SHALL create fixture mock_successful_create_response() returning valid KoraPay virtual account response
8. THE Test_Suite SHALL create fixture mock_successful_confirm_response() returning confirmed transfer response
9. THE Test_Suite SHALL create fixture mock_pending_confirm_response() returning processing status response
10. THE Test_Suite SHALL test create_virtual_account with valid inputs returns expected dict structure
11. THE Test_Suite SHALL test create_virtual_account validates amount is positive
12. THE Test_Suite SHALL test create_virtual_account validates amount is within limits (100 to 999999999)
13. THE Test_Suite SHALL test create_virtual_account validates reference length >= 8 characters
14. THE Test_Suite SHALL test create_virtual_account validates customer_email format
15. THE Test_Suite SHALL test create_virtual_account includes all required request headers
16. THE Test_Suite SHALL test create_virtual_account constructs correct request body structure
17. THE Test_Suite SHALL test create_virtual_account handles HTTP 400 with field validation errors
18. THE Test_Suite SHALL test create_virtual_account handles HTTP 401 authentication failure
19. THE Test_Suite SHALL test create_virtual_account handles HTTP 429 rate limit with Retry-After
20. THE Test_Suite SHALL test create_virtual_account handles HTTP 500 with retry logic
21. THE Test_Suite SHALL test create_virtual_account handles timeout with retry logic
22. THE Test_Suite SHALL test create_virtual_account handles connection error with retry logic
23. THE Test_Suite SHALL test create_virtual_account handles SSL error without retry
24. THE Test_Suite SHALL test create_virtual_account handles JSON decode error
25. THE Test_Suite SHALL test create_virtual_account validates all required response fields present
26. THE Test_Suite SHALL test create_virtual_account validates response amount matches request
27. THE Test_Suite SHALL test create_virtual_account validates response reference matches request
28. THE Test_Suite SHALL test create_virtual_account normalizes response to backward-compatible format
29. THE Test_Suite SHALL test create_virtual_account logs request and response at INFO level
30. THE Test_Suite SHALL test create_virtual_account masks API key in logs

**Unit Test Coverage - Transfer Confirmation:**

31. THE Test_Suite SHALL test confirm_transfer with valid reference returns expected dict
32. THE Test_Suite SHALL test confirm_transfer handles "success" status correctly
33. THE Test_Suite SHALL test confirm_transfer handles "processing" status correctly
34. THE Test_Suite SHALL test confirm_transfer handles "failed" status correctly
35. THE Test_Suite SHALL test confirm_transfer maps KoraPay status to responseCode correctly
36. THE Test_Suite SHALL test confirm_transfer handles HTTP 404 transaction not found
37. THE Test_Suite SHALL test confirm_transfer handles HTTP 500 with retry
38. THE Test_Suite SHALL test confirm_transfer handles timeout with retry
39. THE Test_Suite SHALL test confirm_transfer validates response fields
40. THE Test_Suite SHALL test confirm_transfer logs request and response

**Unit Test Coverage - Mock Mode:**

41. THE Test_Suite SHALL test mock mode activates when KORAPAY_SECRET_KEY is empty
42. THE Test_Suite SHALL test mock mode generates deterministic account numbers
43. THE Test_Suite SHALL test mock mode account number formula produces valid 10-digit numbers
44. THE Test_Suite SHALL test mock mode returns "Z0" for first 3 polls
45. THE Test_Suite SHALL test mock mode returns "00" on 4th poll
46. THE Test_Suite SHALL test mock mode increments poll counter correctly
47. THE Test_Suite SHALL test mock mode cleans up poll counter after confirmation
48. THE Test_Suite SHALL test mock mode handles concurrent polls for different transactions
49. THE Test_Suite SHALL test mock mode reset_mock_state() clears all counters
50. THE Test_Suite SHALL test mock mode special prefixes trigger appropriate errors (MOCK-FAIL-, MOCK-TIMEOUT-, etc.)
51. THE Test_Suite SHALL test mock mode respects KORAPAY_MOCK_CONFIRM_AFTER configuration
52. THE Test_Suite SHALL test mock mode respects KORAPAY_MOCK_DELAY_MS configuration
53. THE Test_Suite SHALL test mock mode calculates realistic fees (1.5% + 7.5% VAT)
54. THE Test_Suite SHALL test mock mode generates valid expiry timestamps (30 minutes future)
55. THE Test_Suite SHALL test mock mode never makes real HTTP requests

**Unit Test Coverage - Error Handling:**

56. THE Test_Suite SHALL test retry logic executes exactly 3 attempts for 500 errors
57. THE Test_Suite SHALL test retry delays are 1s, 2s, 4s with jitter
58. THE Test_Suite SHALL test retry logic stops after 3 attempts and raises KoraPayError
59. THE Test_Suite SHALL test 4xx errors are not retried (except 429)
60. THE Test_Suite SHALL test 429 errors use Retry-After header when present
61. THE Test_Suite SHALL test 429 errors default to 60s delay when Retry-After missing
62. THE Test_Suite SHALL test SSL errors are not retried
63. THE Test_Suite SHALL test DNS errors are not retried
64. THE Test_Suite SHALL test connection errors are retried
65. THE Test_Suite SHALL test timeout errors are retried
66. THE Test_Suite SHALL test JSON decode errors raise KoraPayError immediately
67. THE Test_Suite SHALL test missing required fields raise KoraPayError with field list
68. THE Test_Suite SHALL test wrong field types raise KoraPayError with type info
69. THE Test_Suite SHALL test amount mismatch raises KoraPayError
70. THE Test_Suite SHALL test reference mismatch raises KoraPayError


### Requirement 35: Implement Detailed Sandbox Testing Procedures

**User Story:** As a developer, I want detailed sandbox testing procedures with test data and expected results, so that I can verify the integration before production deployment.

#### Acceptance Criteria

**Sandbox Configuration:**

1. THE System SHALL support sandbox mode by setting KORAPAY_USE_SANDBOX=true in environment
2. THE System SHALL use sandbox API keys starting with "sk_test_" prefix
3. THE System SHALL use same base URL for sandbox and production (https://api.korapay.com)
4. THE System SHALL differentiate sandbox vs production by API key prefix only
5. THE System SHALL log "KoraPay SANDBOX mode active" at startup when using test keys
6. THE System SHALL display sandbox indicator in merchant dashboard when KORAPAY_USE_SANDBOX is true
7. THE System SHALL add visual warning banner "SANDBOX MODE - Test transactions only" in UI
8. THE System SHALL prevent accidental production transactions in sandbox mode

**Sandbox Auto-Complete Feature:**

9. THE System SHALL support auto_complete field in virtual account creation request (sandbox only)
10. THE System SHALL set auto_complete=true in request body to enable automatic payment after 2 minutes
11. THE System SHALL set auto_complete=false to require manual test payment trigger
12. THE System SHALL default auto_complete=true in sandbox for automated testing
13. THE System SHALL log "Sandbox auto-complete enabled | ref={ref} will_confirm_in=2min" when auto_complete is true
14. WHEN auto_complete is true, THE System SHALL expect payment confirmation after 2 minutes without manual action
15. THE System SHALL document auto_complete behavior in sandbox testing guide

**Sandbox Test Bank Accounts:**

16. THE System SHALL document test bank account 033-0000000000 triggers successful payment in sandbox
17. THE System SHALL document test bank account 035-0000000000 triggers failed payment in sandbox
18. THE System SHALL create test procedure: "Transfer from 033-0000000000 to verify success flow"
19. THE System SHALL create test procedure: "Transfer from 035-0000000000 to verify failure handling"
20. THE System SHALL document that sandbox payments are not real and no money is transferred
21. THE System SHALL document that sandbox virtual accounts expire after 30 minutes like production
22. THE System SHALL document that sandbox supports all API endpoints available in production
23. THE System SHALL document that sandbox webhook signatures use same algorithm as production
24. THE System SHALL validate sandbox webhook signatures using KORAPAY_WEBHOOK_SECRET (same as production)

**Sandbox Test Scenarios:**

25. THE Test_Suite SHALL create test scenario "Happy Path - Successful Payment" with steps:
    - Create payment link with amount ₦1,000
    - Verify virtual account created with Wema/Sterling/Providus bank
    - Wait 2 minutes for auto-complete OR manually trigger
    - Poll transfer status, expect "processing" then "success"
    - Verify transaction status updated to VERIFIED
    - Verify webhook delivered if configured
    - Verify merchant email sent
    - Verify customer invoice email sent if enabled
26. THE Test_Suite SHALL create test scenario "Failed Payment" with steps:
    - Create payment link
    - Trigger failure using test bank account 035-0000000000
    - Poll transfer status, expect "failed"
    - Verify transaction status updated to FAILED
    - Verify failure reason stored
    - Verify merchant notified of failure
27. THE Test_Suite SHALL create test scenario "Expired Payment Link" with steps:
    - Create payment link with 1-minute expiry
    - Wait for expiry
    - Attempt to poll status, expect "expired" response
    - Verify transaction status updated to EXPIRED
28. THE Test_Suite SHALL create test scenario "Webhook Delivery" with steps:
    - Create payment link with webhook URL
    - Trigger payment confirmation
    - Verify webhook POST sent to configured URL
    - Verify webhook signature is valid
    - Verify webhook payload contains all required fields
29. THE Test_Suite SHALL create test scenario "Refund Processing" with steps:
    - Create and confirm payment
    - Initiate refund for full amount
    - Query refund status, expect "processing" then "success"
    - Verify transaction status updated to REFUNDED
    - Verify refund record created in database
30. THE Test_Suite SHALL document expected response times for each scenario
31. THE Test_Suite SHALL document expected log messages for each scenario
32. THE Test_Suite SHALL document expected database state after each scenario
33. THE Test_Suite SHALL create automated test script that runs all scenarios
34. THE Test_Suite SHALL validate all scenarios pass before production deployment


### Requirement 36: Implement Detailed Security Audit and Penetration Testing Requirements

**User Story:** As a security engineer, I want comprehensive security testing for the KoraPay integration, so that vulnerabilities are identified and fixed before production deployment.

#### Acceptance Criteria

**Authentication Security Testing:**

1. THE Security_Test_Suite SHALL test that KORAPAY_SECRET_KEY is never logged in plain text
2. THE Security_Test_Suite SHALL test that KORAPAY_SECRET_KEY is never exposed in error messages
3. THE Security_Test_Suite SHALL test that KORAPAY_SECRET_KEY is never exposed in API responses
4. THE Security_Test_Suite SHALL test that invalid API key format is rejected at startup
5. THE Security_Test_Suite SHALL test that empty API key in production aborts startup
6. THE Security_Test_Suite SHALL test that test API key in production aborts startup
7. THE Security_Test_Suite SHALL test that API key masking shows only first 4 and last 4 characters
8. THE Security_Test_Suite SHALL test that Authorization header is never logged
9. THE Security_Test_Suite SHALL test that requests use HTTPS in production (verify=True)
10. THE Security_Test_Suite SHALL test that SSL certificate validation cannot be disabled

**Webhook Security Testing:**

11. THE Security_Test_Suite SHALL test webhook signature verification rejects invalid signatures
12. THE Security_Test_Suite SHALL test webhook signature verification uses constant-time comparison
13. THE Security_Test_Suite SHALL test webhook signature is computed on data object only (not full payload)
14. THE Security_Test_Suite SHALL test webhook with missing signature header returns HTTP 401
15. THE Security_Test_Suite SHALL test webhook with wrong signature returns HTTP 401
16. THE Security_Test_Suite SHALL test webhook with tampered payload returns HTTP 401
17. THE Security_Test_Suite SHALL test webhook timestamp validation rejects old webhooks (>5 minutes)
18. THE Security_Test_Suite SHALL test webhook replay attack is prevented by timestamp check
19. THE Security_Test_Suite SHALL test webhook from private IP is rejected
20. THE Security_Test_Suite SHALL test webhook from localhost is rejected
21. THE Security_Test_Suite SHALL test webhook from AWS metadata IP (169.254.169.254) is rejected
22. THE Security_Test_Suite SHALL test webhook signature verification logs failed attempts
23. THE Security_Test_Suite SHALL test webhook signature verification creates audit log entry
24. THE Security_Test_Suite SHALL test webhook idempotency prevents duplicate processing
25. THE Security_Test_Suite SHALL test webhook rate limiting prevents flooding attacks

**Input Validation Security Testing:**

26. THE Security_Test_Suite SHALL test SQL injection attempts in transaction_reference are blocked
27. THE Security_Test_Suite SHALL test XSS attempts in account_name are sanitized
28. THE Security_Test_Suite SHALL test XSS attempts in customer_name are sanitized
29. THE Security_Test_Suite SHALL test XSS attempts in description are sanitized
30. THE Security_Test_Suite SHALL test command injection attempts in narration are blocked
31. THE Security_Test_Suite SHALL test path traversal attempts in reference are blocked
32. THE Security_Test_Suite SHALL test null byte injection in string fields is blocked
33. THE Security_Test_Suite SHALL test oversized inputs are rejected (max length validation)
34. THE Security_Test_Suite SHALL test negative amounts are rejected
35. THE Security_Test_Suite SHALL test zero amounts are rejected
36. THE Security_Test_Suite SHALL test amounts exceeding maximum are rejected
37. THE Security_Test_Suite SHALL test invalid email formats are rejected
38. THE Security_Test_Suite SHALL test invalid phone formats are rejected
39. THE Security_Test_Suite SHALL test invalid URL formats are rejected
40. THE Security_Test_Suite SHALL test malformed JSON in webhook payload is rejected

**SSRF and DNS Rebinding Protection Testing:**

41. THE Security_Test_Suite SHALL test webhook URL validation rejects private IPs (10.0.0.0/8)
42. THE Security_Test_Suite SHALL test webhook URL validation rejects private IPs (172.16.0.0/12)
43. THE Security_Test_Suite SHALL test webhook URL validation rejects private IPs (192.168.0.0/16)
44. THE Security_Test_Suite SHALL test webhook URL validation rejects localhost (127.0.0.1, ::1)
45. THE Security_Test_Suite SHALL test webhook URL validation rejects link-local (169.254.0.0/16)
46. THE Security_Test_Suite SHALL test webhook URL validation rejects AWS metadata endpoint
47. THE Security_Test_Suite SHALL test DNS rebinding attack is prevented by re-validating DNS on each attempt
48. THE Security_Test_Suite SHALL test webhook URL that resolves to private IP after initial validation is blocked
49. THE Security_Test_Suite SHALL test malicious webhook URLs are permanently blacklisted
50. THE Security_Test_Suite SHALL test blacklisted URLs cannot be used even after DNS changes

**Race Condition and Concurrency Testing:**

51. THE Security_Test_Suite SHALL test concurrent payment confirmations do not cause duplicate processing
52. THE Security_Test_Suite SHALL test optimistic locking prevents race conditions in status updates
53. THE Security_Test_Suite SHALL test concurrent webhook deliveries are handled safely
54. THE Security_Test_Suite SHALL test concurrent refund requests are handled safely
55. THE Security_Test_Suite SHALL test database transaction rollback on concurrent update conflicts
56. THE Security_Test_Suite SHALL test poll counter in mock mode is thread-safe
57. THE Security_Test_Suite SHALL test metrics counters are thread-safe
58. THE Security_Test_Suite SHALL simulate 10 concurrent confirmation requests for same transaction
59. THE Security_Test_Suite SHALL verify only one confirmation succeeds and others return idempotent response
60. THE Security_Test_Suite SHALL verify no data corruption occurs under concurrent load

**Information Disclosure Testing:**

61. THE Security_Test_Suite SHALL test error messages do not expose internal paths
62. THE Security_Test_Suite SHALL test error messages do not expose database schema
63. THE Security_Test_Suite SHALL test error messages do not expose API keys or secrets
64. THE Security_Test_Suite SHALL test error messages do not expose stack traces in production
65. THE Security_Test_Suite SHALL test 500 errors return generic message to users
66. THE Security_Test_Suite SHALL test detailed errors are logged internally but not exposed
67. THE Security_Test_Suite SHALL test health check does not expose sensitive configuration
68. THE Security_Test_Suite SHALL test health check does not expose API keys
69. THE Security_Test_Suite SHALL test debug mode is disabled in production
70. THE Security_Test_Suite SHALL test verbose logging is disabled in production


### Requirement 37: Implement Detailed Performance Benchmarking and Optimization

**User Story:** As a performance engineer, I want detailed performance benchmarks and optimization requirements, so that the KoraPay integration meets response time SLAs.

#### Acceptance Criteria

**Performance Benchmarks - Response Time SLAs:**

1. THE System SHALL complete virtual account creation in under 2000ms at 95th percentile
2. THE System SHALL complete virtual account creation in under 1000ms at 50th percentile (median)
3. THE System SHALL complete virtual account creation in under 500ms at 25th percentile
4. THE System SHALL complete transfer status query in under 1000ms at 95th percentile
5. THE System SHALL complete transfer status query in under 500ms at 50th percentile
6. THE System SHALL complete transfer status query in under 250ms at 25th percentile
7. THE System SHALL complete webhook processing in under 500ms at 95th percentile
8. THE System SHALL complete webhook processing in under 200ms at 50th percentile
9. THE System SHALL complete webhook processing in under 100ms at 25th percentile
10. THE System SHALL measure and log response times for all KoraPay API calls
11. THE System SHALL track response time percentiles using collections.deque with maxlen=1000
12. THE System SHALL calculate percentiles using numpy.percentile() or manual implementation
13. THE System SHALL expose performance metrics via /health endpoint
14. THE System SHALL log WARNING when 95th percentile exceeds SLA thresholds

**Connection Pooling and Reuse:**

15. THE System SHALL create requests.Session instance in KoraPay_Service.__init__()
16. THE System SHALL configure Session with HTTPAdapter(pool_connections=10, pool_maxsize=10)
17. THE System SHALL mount HTTPAdapter for both http:// and https:// schemes
18. THE System SHALL reuse Session instance for all API requests (no new Session per request)
19. THE System SHALL enable HTTP keep-alive by setting Connection: keep-alive header
20. THE System SHALL configure Session timeout at session level, not per-request
21. THE System SHALL measure connection reuse rate (reused connections / total requests)
22. THE System SHALL log "HTTP connection pool stats | active={active} idle={idle} reuse_rate={rate}%"
23. WHEN connection reuse rate < 80%, THE System SHALL log WARNING "Low connection reuse"

**Database Query Optimization:**

24. THE System SHALL use SELECT specific columns instead of SELECT * for transaction queries
25. THE System SHALL use database indexes for all WHERE clause fields (tx_ref, user_id, status, created_at)
26. THE System SHALL implement query result caching for frequently accessed data (user settings, invoice settings)
27. THE System SHALL set cache TTL to 300 seconds (5 minutes) for user settings
28. THE System SHALL invalidate cache on updates to cached data
29. THE System SHALL use lazy loading for transaction.user relationship to avoid N+1 queries
30. THE System SHALL use joinedload() for eager loading when user data is always needed
31. THE System SHALL limit transaction history queries to 1000 records maximum
32. THE System SHALL implement cursor-based pagination using created_at + id for stable ordering
33. THE System SHALL log slow queries (>1000ms) at WARNING level with query text and duration
34. THE System SHALL use EXPLAIN ANALYZE in development to profile query performance
35. THE System SHALL create composite index idx_user_created ON transactions(user_id, created_at DESC) for history queries

**Async Processing and Background Tasks:**

36. THE System SHALL implement async webhook delivery using threading.Thread for non-blocking operation
37. THE System SHALL set thread daemon=True to allow graceful shutdown
38. THE System SHALL limit concurrent webhook threads to 10 using threading.Semaphore
39. THE System SHALL queue webhook deliveries when thread limit reached
40. THE System SHALL implement webhook queue using queue.Queue with maxsize=100
41. WHEN webhook queue is full, THE System SHALL log ERROR "Webhook queue full" and drop oldest
42. THE System SHALL implement background thread for retrying failed webhooks every 5 minutes
43. THE System SHALL implement background thread for cleaning up expired transactions every hour
44. THE System SHALL implement background thread for aggregating metrics every 60 seconds
45. THE System SHALL use threading.Event for graceful shutdown signaling
46. THE System SHALL wait for all webhook threads to complete on shutdown (max 30 seconds)
47. THE System SHALL log "Background threads started | webhook_workers=10 retry_worker=1 cleanup_worker=1"

**Caching Strategy:**

48. THE System SHALL implement in-memory cache using dict with threading.Lock for thread safety
49. THE System SHALL cache KoraPay health status for 60 seconds to reduce health check frequency
50. THE System SHALL cache user settings for 300 seconds to reduce database queries
51. THE System SHALL cache invoice settings for 300 seconds to reduce database queries
52. THE System SHALL implement cache invalidation on updates using cache key deletion
53. THE System SHALL implement cache expiry using timestamp comparison
54. THE System SHALL implement cache size limit of 1000 entries using LRU eviction
55. THE System SHALL log cache hit rate every 1000 requests: "Cache stats | hits={hits} misses={misses} hit_rate={rate}%"
56. WHEN cache hit rate < 70%, THE System SHALL log WARNING "Low cache hit rate"

**Load Testing Requirements:**

57. THE System SHALL support load testing with 100 concurrent users creating payment links
58. THE System SHALL support load testing with 1000 concurrent status polls
59. THE System SHALL support load testing with 100 concurrent webhook deliveries
60. THE System SHALL maintain response time SLAs under load (95th percentile < 2x normal)
61. THE System SHALL not crash or return errors under sustained load
62. THE System SHALL implement graceful degradation under extreme load (queue requests, return 503)
63. THE System SHALL log performance metrics during load testing
64. THE System SHALL document load testing procedure in docs/PERFORMANCE_TESTING.md
65. THE System SHALL document expected throughput: 100 payment links/minute, 1000 status polls/minute


### Requirement 38: Implement Detailed Monitoring, Alerting, and Observability

**User Story:** As a site reliability engineer, I want comprehensive monitoring and alerting for the KoraPay integration, so that I can detect and respond to issues proactively.

#### Acceptance Criteria

**Metrics Collection:**

1. THE System SHALL implement metrics collection class KoraPayMetrics with thread-safe counters
2. THE Metrics_Collector SHALL track counter "korapay_api_requests_total" with labels: endpoint, method, status_code
3. THE Metrics_Collector SHALL track counter "korapay_api_errors_total" with labels: endpoint, error_type
4. THE Metrics_Collector SHALL track histogram "korapay_api_duration_seconds" with buckets: 0.1, 0.5, 1.0, 2.0, 5.0, 10.0
5. THE Metrics_Collector SHALL track counter "korapay_virtual_accounts_created_total" with labels: status
6. THE Metrics_Collector SHALL track counter "korapay_transfers_confirmed_total" with labels: method (poll/webhook)
7. THE Metrics_Collector SHALL track counter "korapay_webhooks_received_total" with labels: event_type, status
8. THE Metrics_Collector SHALL track counter "korapay_webhook_signature_failures_total"
9. THE Metrics_Collector SHALL track counter "korapay_retries_total" with labels: endpoint, attempt_number
10. THE Metrics_Collector SHALL track gauge "korapay_api_success_rate" calculated as successes / total over last 100 requests
11. THE Metrics_Collector SHALL track gauge "korapay_api_avg_response_time_ms" calculated over last 100 requests
12. THE Metrics_Collector SHALL track gauge "korapay_api_failures_last_hour" using sliding time window
13. THE Metrics_Collector SHALL use threading.Lock for thread-safe counter updates
14. THE Metrics_Collector SHALL use collections.deque with maxlen for sliding windows
15. THE Metrics_Collector SHALL implement method get_metrics() -> dict returning all current metric values

**Health Check Enhancements:**

16. THE Health_Check_Endpoint SHALL include field "korapay_api_success_rate" as percentage (0-100)
17. THE Health_Check_Endpoint SHALL include field "korapay_api_avg_response_time_ms" as integer milliseconds
18. THE Health_Check_Endpoint SHALL include field "korapay_api_failures_last_hour" as integer count
19. THE Health_Check_Endpoint SHALL include field "korapay_api_status" with values: "healthy", "degraded", "down"
20. THE Health_Check_Endpoint SHALL include field "korapay_mode" with values: "production", "sandbox", "mock"
21. THE Health_Check_Endpoint SHALL include field "korapay_base_url" showing active endpoint (without credentials)
22. THE Health_Check_Endpoint SHALL include field "korapay_last_success_at" as ISO timestamp of last successful API call
23. THE Health_Check_Endpoint SHALL include field "korapay_last_failure_at" as ISO timestamp of last failed API call
24. THE Health_Check_Endpoint SHALL include field "korapay_consecutive_failures" as integer count
25. THE Health_Check_Endpoint SHALL calculate korapay_api_status based on success_rate and avg_response_time
26. WHEN success_rate >= 95% AND avg_response_time < 5000ms, THE Health_Check_Endpoint SHALL set status "healthy"
27. WHEN success_rate >= 80% OR avg_response_time < 10000ms, THE Health_Check_Endpoint SHALL set status "degraded"
28. WHEN success_rate < 80% OR consecutive_failures > 10, THE Health_Check_Endpoint SHALL set status "down"
29. THE Health_Check_Endpoint SHALL include field "korapay_connection_pool_stats" with active and idle connection counts
30. THE Health_Check_Endpoint SHALL include field "korapay_webhook_queue_size" showing pending webhook deliveries

**Alerting Rules:**

31. WHEN korapay_api_success_rate < 95% over 100 requests, THE System SHALL log CRITICAL "KoraPay API success rate below threshold | rate={rate}% threshold=95%"
32. WHEN korapay_api_avg_response_time_ms > 5000 over 10 requests, THE System SHALL log WARNING "KoraPay API slow response | avg={avg}ms threshold=5000ms"
33. WHEN korapay_api_failures_last_hour > 10, THE System SHALL log CRITICAL "KoraPay API high failure rate | failures={count} threshold=10"
34. WHEN korapay_webhook_signature_failures_total > 5 in last hour, THE System SHALL log CRITICAL "Multiple webhook signature failures - possible attack | count={count}"
35. WHEN korapay_consecutive_failures > 5, THE System SHALL log ERROR "KoraPay API consecutive failures | count={count}"
36. WHEN korapay_consecutive_failures > 10, THE System SHALL log CRITICAL "KoraPay API may be down | consecutive_failures={count}"
37. WHEN korapay_webhook_queue_size > 50, THE System SHALL log WARNING "Webhook queue backing up | size={size}"
38. WHEN korapay_webhook_queue_size > 90, THE System SHALL log CRITICAL "Webhook queue near capacity | size={size}"
39. THE System SHALL implement alert deduplication to prevent alert spam (max 1 alert per 5 minutes per rule)
40. THE System SHALL implement alert escalation: WARNING -> ERROR -> CRITICAL based on duration

**Structured Logging for Observability:**

41. THE System SHALL implement structured logging using JSON format for all KoraPay operations
42. THE System SHALL include fields in every log: timestamp, level, component, operation, tx_ref, user_id, ip_address, request_id, duration_ms
43. THE System SHALL use component="korapay" for all KoraPay-related logs
44. THE System SHALL use operation values: "create_account", "confirm_transfer", "webhook_received", "refund_initiated"
45. THE System SHALL include correlation_id field for tracing requests across services
46. THE System SHALL include session_id field for tracing user sessions
47. THE System SHALL implement log aggregation tags for filtering: environment, service, component, operation, status
48. THE System SHALL write KoraPay logs to separate file logs/korapay.log for easy analysis
49. THE System SHALL write security logs to separate file logs/korapay_security.log
50. THE System SHALL implement log rotation: max 100MB per file, keep 10 files, compress old files using gzip
51. THE System SHALL implement log shipping to external service (optional: Elasticsearch, CloudWatch, Datadog)
52. THE System SHALL document log analysis queries in docs/MONITORING.md
53. THE System SHALL document alert thresholds and escalation procedures in docs/MONITORING.md
54. THE System SHALL create dashboard queries for: success rate, response time, error rate, webhook failures
55. THE System SHALL document on-call runbook for KoraPay integration issues


### Requirement 39: Implement Detailed Deployment Checklist and Procedures

**User Story:** As a DevOps engineer, I want a detailed deployment checklist with verification steps, so that I can deploy the KoraPay integration safely without missing critical steps.

#### Acceptance Criteria

**Pre-Deployment Checklist:**

1. THE Deployment_Checklist SHALL verify all unit tests pass: pytest tests/unit/test_korapay_service.py -v
2. THE Deployment_Checklist SHALL verify all integration tests pass: pytest tests/integration/test_korapay_flow.py -v
3. THE Deployment_Checklist SHALL verify code coverage >= 95% for services/korapay.py
4. THE Deployment_Checklist SHALL verify no linting errors: ruff check services/korapay.py
5. THE Deployment_Checklist SHALL verify no type errors: mypy services/korapay.py (if type hints used)
6. THE Deployment_Checklist SHALL verify security audit passes: python scripts/security_audit.py
7. THE Deployment_Checklist SHALL verify KoraPay sandbox testing completed successfully
8. THE Deployment_Checklist SHALL verify all sandbox test scenarios pass (happy path, failure, expiry, webhook, refund)
9. THE Deployment_Checklist SHALL verify KoraPay production API keys obtained from dashboard
10. THE Deployment_Checklist SHALL verify KORAPAY_SECRET_KEY starts with "sk_live_" prefix
11. THE Deployment_Checklist SHALL verify KORAPAY_WEBHOOK_SECRET generated with secrets.token_hex(32)
12. THE Deployment_Checklist SHALL verify KORAPAY_WEBHOOK_URL configured in KoraPay dashboard
13. THE Deployment_Checklist SHALL verify webhook endpoint is publicly accessible (test with curl)
14. THE Deployment_Checklist SHALL verify SSL certificate is valid for webhook endpoint
15. THE Deployment_Checklist SHALL verify database backup created and verified
16. THE Deployment_Checklist SHALL verify rollback procedure tested in staging
17. THE Deployment_Checklist SHALL verify monitoring and alerting configured
18. THE Deployment_Checklist SHALL verify on-call engineer assigned and notified
19. THE Deployment_Checklist SHALL verify merchant notification email drafted
20. THE Deployment_Checklist SHALL verify maintenance window scheduled (off-peak hours)

**Deployment Steps:**

21. THE Deployment_Procedure SHALL execute step 1: Send merchant notification 24 hours before maintenance
22. THE Deployment_Procedure SHALL execute step 2: Create database backup using scripts/backup_database.sh
23. THE Deployment_Procedure SHALL execute step 3: Verify backup integrity using scripts/verify_backup.sh
24. THE Deployment_Procedure SHALL execute step 4: Enable maintenance mode (display "Maintenance in progress" page)
25. THE Deployment_Procedure SHALL execute step 5: Wait for all pending transactions to complete or expire (max 30 minutes)
26. THE Deployment_Procedure SHALL execute step 6: Stop Flask application: systemctl stop onepay
27. THE Deployment_Procedure SHALL execute step 7: Pull latest code: git pull origin main
28. THE Deployment_Procedure SHALL execute step 8: Checkout migration branch: git checkout migration/korapay-integration
29. THE Deployment_Procedure SHALL execute step 9: Install dependencies: pip install -r requirements.txt
30. THE Deployment_Procedure SHALL execute step 10: Run database migrations: alembic upgrade head
31. THE Deployment_Procedure SHALL execute step 11: Update environment variables in .env file
32. THE Deployment_Procedure SHALL execute step 12: Validate configuration: python -c "from config import Config; Config.validate()"
33. THE Deployment_Procedure SHALL execute step 13: Run migration script: python scripts/migrate_to_korapay.py
34. THE Deployment_Procedure SHALL execute step 14: Verify migration: python scripts/verify_migration.py
35. THE Deployment_Procedure SHALL execute step 15: Start Flask application: systemctl start onepay
36. THE Deployment_Procedure SHALL execute step 16: Check application logs: tail -f logs/application.log
37. THE Deployment_Procedure SHALL execute step 17: Test health check: curl https://domain.com/health
38. THE Deployment_Procedure SHALL execute step 18: Create test payment link in production
39. THE Deployment_Procedure SHALL execute step 19: Verify virtual account created successfully
40. THE Deployment_Procedure SHALL execute step 20: Disable maintenance mode

**Post-Deployment Verification:**

41. THE Deployment_Procedure SHALL execute smoke test: Create payment link and verify virtual account
42. THE Deployment_Procedure SHALL execute smoke test: Poll transfer status and verify response format
43. THE Deployment_Procedure SHALL execute smoke test: Trigger webhook and verify signature validation
44. THE Deployment_Procedure SHALL execute smoke test: Check health endpoint shows korapay status
45. THE Deployment_Procedure SHALL execute smoke test: Verify mock mode disabled in production
46. THE Deployment_Procedure SHALL monitor error logs for 1 hour after deployment
47. THE Deployment_Procedure SHALL monitor KoraPay API success rate for 1 hour
48. THE Deployment_Procedure SHALL monitor response times for 1 hour
49. THE Deployment_Procedure SHALL verify no 500 errors in first hour
50. THE Deployment_Procedure SHALL verify no authentication failures in first hour
51. THE Deployment_Procedure SHALL verify webhook deliveries working correctly
52. THE Deployment_Procedure SHALL verify merchant emails sending correctly
53. THE Deployment_Procedure SHALL verify customer invoice emails sending correctly
54. THE Deployment_Procedure SHALL verify QR codes generating correctly
55. THE Deployment_Procedure SHALL verify transaction history displaying correctly
56. THE Deployment_Procedure SHALL verify CSV export working correctly
57. THE Deployment_Procedure SHALL verify audit logs recording events correctly
58. THE Deployment_Procedure SHALL document verification results in deployment_verification_YYYYMMDD.md
59. THE Deployment_Procedure SHALL send "Deployment successful" notification to merchants after 1 hour
60. THE Deployment_Procedure SHALL schedule post-deployment review meeting for next business day

**Rollback Decision Criteria:**

61. THE Rollback_Criteria SHALL trigger rollback IF migration verification fails
62. THE Rollback_Criteria SHALL trigger rollback IF application fails to start after migration
63. THE Rollback_Criteria SHALL trigger rollback IF health check shows "down" status for > 5 minutes
64. THE Rollback_Criteria SHALL trigger rollback IF success rate < 80% in first hour
65. THE Rollback_Criteria SHALL trigger rollback IF > 10 critical errors in first hour
66. THE Rollback_Criteria SHALL trigger rollback IF webhook signature verification fails for all webhooks
67. THE Rollback_Criteria SHALL trigger rollback IF database corruption detected
68. THE Rollback_Criteria SHALL trigger rollback IF merchant reports payment failures
69. THE Rollback_Criteria SHALL document rollback decision authority (who can authorize rollback)
70. THE Rollback_Criteria SHALL document rollback execution time: 15-30 minutes
71. THE Rollback_Criteria SHALL document rollback procedure: execute scripts/rollback_to_quickteller.py
72. THE Rollback_Criteria SHALL document post-rollback communication plan


### Requirement 40: Implement Detailed Reconciliation and Data Consistency Checks

**User Story:** As a finance manager, I want automated reconciliation between OnePay and KoraPay records, so that I can detect and resolve discrepancies quickly.

#### Acceptance Criteria

**Daily Reconciliation Process:**

1. THE System SHALL implement reconciliation script scripts/reconcile_korapay.py running daily via cron
2. THE Reconciliation_Script SHALL query all transactions from last 7 days with status VERIFIED
3. THE Reconciliation_Script SHALL query KoraPay API for each transaction using merchant reference
4. THE Reconciliation_Script SHALL compare local transaction.amount with KoraPay data.amount
5. WHEN amounts differ, THE Reconciliation_Script SHALL log ERROR "Amount mismatch | ref={ref} local={local} korapay={kp}"
6. THE Reconciliation_Script SHALL compare local transaction.status with KoraPay data.status
7. WHEN statuses differ, THE Reconciliation_Script SHALL log WARNING "Status mismatch | ref={ref} local={local} korapay={kp}"
8. THE Reconciliation_Script SHALL compare local transaction.provider_fee with KoraPay data.fee
9. WHEN fees differ, THE Reconciliation_Script SHALL log WARNING "Fee mismatch | ref={ref} local={local} korapay={kp}"
10. THE Reconciliation_Script SHALL identify transactions in local DB but not in KoraPay
11. WHEN transaction missing from KoraPay, THE Reconciliation_Script SHALL log ERROR "Orphaned transaction | ref={ref}"
12. THE Reconciliation_Script SHALL identify transactions in KoraPay but not in local DB
13. WHEN transaction missing from local DB, THE Reconciliation_Script SHALL log CRITICAL "Missing transaction | ref={ref}"
14. THE Reconciliation_Script SHALL calculate total amount reconciled: sum of all verified transactions
15. THE Reconciliation_Script SHALL calculate total fees paid: sum of all provider_fee values
16. THE Reconciliation_Script SHALL generate reconciliation report with: date, transactions_checked, mismatches_found, total_amount, total_fees
17. THE Reconciliation_Script SHALL export report to reports/reconciliation_YYYYMMDD.json
18. THE Reconciliation_Script SHALL send email to finance team with reconciliation summary
19. WHEN mismatches found, THE Reconciliation_Script SHALL send alert email with details
20. THE Reconciliation_Script SHALL log "Reconciliation complete | checked={count} mismatches={mismatches} status=OK"

**Real-Time Consistency Checks:**

21. WHEN confirming payment, THE System SHALL validate KoraPay response amount matches local transaction amount
22. WHEN confirming payment, THE System SHALL validate KoraPay response reference matches local tx_ref
23. WHEN confirming payment, THE System SHALL validate KoraPay response currency is "NGN"
24. WHEN validation fails, THE System SHALL log CRITICAL "Data consistency error" and abort confirmation
25. WHEN validation fails, THE System SHALL send alert to on-call engineer
26. THE System SHALL implement double-entry bookkeeping check: debits = credits for all transactions
27. THE System SHALL validate transaction state transitions are valid (PENDING -> VERIFIED, not VERIFIED -> PENDING)
28. THE System SHALL validate timestamps are monotonic (verified_at >= created_at)
29. THE System SHALL validate foreign key integrity (transaction.user_id exists in users table)
30. THE System SHALL run consistency checks on startup and log results


### Requirement 41: Implement Detailed Rate Limiting and Abuse Prevention

**User Story:** As a security engineer, I want comprehensive rate limiting for all KoraPay operations, so that abuse and DoS attacks are prevented.

#### Acceptance Criteria

**Rate Limiting - Virtual Account Creation:**

1. THE System SHALL implement rate limit of 10 payment link creations per minute per user_id
2. THE System SHALL implement rate limit of 100 payment link creations per hour per user_id
3. THE System SHALL implement rate limit of 50 payment link creations per minute per IP address
4. WHEN user rate limit exceeded, THE System SHALL return HTTP 429 with JSON {"error": "Rate limit exceeded", "code": "RATE_LIMIT", "retry_after": 60}
5. WHEN user rate limit exceeded, THE System SHALL log WARNING "Payment link creation rate limit | user_id={id} limit=10/min"
6. THE System SHALL use existing rate_limiter service with key format "korapay:create:{user_id}"
7. THE System SHALL use sliding window algorithm for rate limiting (not fixed window)
8. THE System SHALL store rate limit counters in database rate_limits table
9. THE System SHALL clean up expired rate limit records older than 24 hours

**Rate Limiting - Transfer Status Polling:**

10. THE System SHALL implement rate limit of 20 status polls per minute per IP address
11. THE System SHALL implement rate limit of 60 status polls per hour per transaction reference
12. WHEN IP rate limit exceeded, THE System SHALL return HTTP 429 with retry_after=60
13. WHEN transaction rate limit exceeded, THE System SHALL return HTTP 429 with retry_after=300
14. THE System SHALL log WARNING "Status polling rate limit | ip={ip} tx_ref={ref} limit=20/min"
15. THE System SHALL use rate limit key format "korapay:poll:{ip}" for IP-based limiting
16. THE System SHALL use rate limit key format "korapay:poll:tx:{ref}" for transaction-based limiting
17. THE System SHALL implement client-side polling cap in JavaScript: max 60 polls per transaction
18. THE System SHALL implement exponential backoff in client polling: 2s, 4s, 8s, 16s, 30s intervals
19. THE System SHALL display "Checking payment status..." message during polling
20. THE System SHALL display "Still waiting for payment..." after 10 polls

**Rate Limiting - Webhook Endpoint:**

21. THE System SHALL implement rate limit of 100 webhook requests per minute per IP address
22. THE System SHALL implement rate limit of 1000 webhook requests per hour per IP address
23. WHEN webhook rate limit exceeded, THE System SHALL return HTTP 429 with retry_after=60
24. THE System SHALL log WARNING "Webhook rate limit exceeded | ip={ip} limit=100/min"
25. THE System SHALL track webhook rate limit violations in security metrics
26. WHEN webhook rate limit violations > 10 per hour from same IP, THE System SHALL blacklist IP
27. THE System SHALL implement IP blacklist with automatic expiry after 24 hours
28. THE System SHALL log CRITICAL "IP blacklisted for webhook abuse | ip={ip} violations={count}"

**Rate Limiting - KoraPay API Calls:**

29. THE System SHALL implement client-side rate limiting to respect KoraPay API limits
30. THE System SHALL limit outbound API requests to 100 per minute (conservative estimate)
31. THE System SHALL implement token bucket algorithm for outbound rate limiting
32. THE System SHALL queue requests when rate limit reached (max queue size 50)
33. WHEN queue is full, THE System SHALL return error "Too many pending requests"
34. THE System SHALL log WARNING "KoraPay API rate limit approaching | requests_last_minute={count}"
35. THE System SHALL track KoraPay rate limit responses (HTTP 429) in metrics
36. WHEN KoraPay returns 429, THE System SHALL back off and reduce request rate
37. THE System SHALL implement adaptive rate limiting based on 429 responses
38. THE System SHALL document KoraPay rate limits in docs/KORAPAY_LIMITS.md


### Requirement 42: Implement Detailed Documentation with Examples and Troubleshooting

**User Story:** As a developer, I want comprehensive documentation with code examples and troubleshooting guides, so that I can understand and maintain the KoraPay integration.

#### Acceptance Criteria

**API Documentation:**

1. THE Documentation SHALL create file docs/KORAPAY_API_REFERENCE.md with complete API specifications
2. THE API_Documentation SHALL document virtual account creation endpoint with full request/response examples
3. THE API_Documentation SHALL document transfer confirmation endpoint with full request/response examples
4. THE API_Documentation SHALL document webhook endpoint with full payload examples
5. THE API_Documentation SHALL document refund endpoint with full request/response examples
6. THE API_Documentation SHALL include curl command examples for each endpoint
7. THE API_Documentation SHALL include Python code examples using requests library
8. THE API_Documentation SHALL include example responses for success cases
9. THE API_Documentation SHALL include example responses for all error cases (400, 401, 404, 429, 500)
10. THE API_Documentation SHALL document all request headers with descriptions
11. THE API_Documentation SHALL document all response fields with data types and descriptions
12. THE API_Documentation SHALL document authentication mechanism with Bearer token example
13. THE API_Documentation SHALL document webhook signature verification algorithm with code example
14. THE API_Documentation SHALL document rate limits for each endpoint
15. THE API_Documentation SHALL document timeout values and retry policies

**Configuration Guide:**

16. THE Documentation SHALL create file docs/KORAPAY_SETUP.md with step-by-step setup instructions
17. THE Setup_Guide SHALL document how to create KoraPay account at https://korapay.com
18. THE Setup_Guide SHALL document how to access KoraPay dashboard
19. THE Setup_Guide SHALL document how to navigate to Settings -> API Configuration
20. THE Setup_Guide SHALL document how to generate API keys (live and test)
21. THE Setup_Guide SHALL document how to copy secret key securely
22. THE Setup_Guide SHALL document how to configure webhook URL in KoraPay dashboard
23. THE Setup_Guide SHALL document how to test webhook endpoint with curl
24. THE Setup_Guide SHALL document how to verify webhook signature manually
25. THE Setup_Guide SHALL document how to switch between sandbox and production
26. THE Setup_Guide SHALL document how to generate KORAPAY_WEBHOOK_SECRET using Python
27. THE Setup_Guide SHALL document how to add configuration to .env file
28. THE Setup_Guide SHALL document how to validate configuration using Config.validate()
29. THE Setup_Guide SHALL document how to test integration in sandbox mode
30. THE Setup_Guide SHALL document how to verify integration is working correctly

**Troubleshooting Guide:**

31. THE Documentation SHALL create file docs/KORAPAY_TROUBLESHOOTING.md with common issues and solutions
32. THE Troubleshooting_Guide SHALL document issue "Authentication failed (HTTP 401)" with solutions:
    - Verify KORAPAY_SECRET_KEY is correct
    - Check API key starts with sk_live_ or sk_test_
    - Verify API key is active in KoraPay dashboard
    - Check environment (production vs sandbox) matches key type
33. THE Troubleshooting_Guide SHALL document issue "Virtual account creation fails" with solutions:
    - Check KoraPay API status at status.korapay.com
    - Verify amount is within limits (₦100 to ₦999,999,999)
    - Check transaction reference is unique and >= 8 characters
    - Review application logs for detailed error
34. THE Troubleshooting_Guide SHALL document issue "Transfer status always pending" with solutions:
    - Verify customer completed bank transfer
    - Check virtual account has not expired
    - Verify correct amount was transferred
    - Check KoraPay dashboard for transaction status
    - Review webhook logs for missed notifications
35. THE Troubleshooting_Guide SHALL document issue "Webhook signature verification fails" with solutions:
    - Verify KORAPAY_WEBHOOK_SECRET matches KoraPay dashboard
    - Check signature is computed on data object only (not full payload)
    - Verify HMAC algorithm is SHA256
    - Test signature computation manually with sample payload
    - Check webhook secret is not same as API secret key
36. THE Troubleshooting_Guide SHALL document issue "Mock mode not working" with solutions:
    - Verify KORAPAY_SECRET_KEY is empty or < 32 characters
    - Check logs for "MOCK MODE ACTIVE" message
    - Verify is_configured() returns False
    - Check poll counter increments correctly
37. THE Troubleshooting_Guide SHALL document issue "Rate limit exceeded" with solutions:
    - Reduce request frequency
    - Implement exponential backoff
    - Check for infinite polling loops
    - Review rate limit configuration
    - Contact KoraPay support for limit increase
38. THE Troubleshooting_Guide SHALL document issue "Slow API responses" with solutions:
    - Check network latency to KoraPay
    - Verify connection pooling is working
    - Check database query performance
    - Review application logs for slow operations
    - Monitor KoraPay API status
39. THE Troubleshooting_Guide SHALL document issue "Database lock timeout" with solutions:
    - Check for long-running transactions
    - Verify optimistic locking is working
    - Review concurrent request handling
    - Check database connection pool size
40. THE Troubleshooting_Guide SHALL include log analysis commands for each issue
41. THE Troubleshooting_Guide SHALL include diagnostic commands (curl, psql, grep)
42. THE Troubleshooting_Guide SHALL include escalation procedures for unresolved issues
43. THE Troubleshooting_Guide SHALL include KoraPay support contact information
44. THE Troubleshooting_Guide SHALL include emergency rollback procedure


### Requirement 43: Implement Detailed Logging Requirements with Structured Format

**User Story:** As a DevOps engineer, I want structured logging with consistent format and searchable fields, so that I can analyze logs efficiently and debug issues quickly.

#### Acceptance Criteria

**Log Format and Structure:**

1. THE System SHALL implement structured logging using JSON format for all KoraPay operations
2. THE System SHALL use log format: {"timestamp": "ISO8601", "level": "INFO", "component": "korapay", "operation": "create_account", "message": "text", "tx_ref": "ref", "user_id": 123, "ip_address": "1.2.3.4", "request_id": "uuid", "duration_ms": 1234, "status": "success"}
3. THE System SHALL include field "timestamp" in ISO 8601 format with timezone (YYYY-MM-DDTHH:MM:SS.sss+00:00)
4. THE System SHALL include field "level" with values: DEBUG, INFO, WARNING, ERROR, CRITICAL
5. THE System SHALL include field "component" with value "korapay" for all KoraPay logs
6. THE System SHALL include field "operation" with values: create_account, confirm_transfer, webhook_received, refund_initiated, health_check
7. THE System SHALL include field "message" with human-readable description
8. THE System SHALL include field "tx_ref" when available (transaction reference)
9. THE System SHALL include field "user_id" when available (merchant user ID)
10. THE System SHALL include field "ip_address" when available (client IP)
11. THE System SHALL include field "request_id" for all API requests (UUID v4)
12. THE System SHALL include field "duration_ms" for all timed operations
13. THE System SHALL include field "status" with values: success, failure, pending, error
14. THE System SHALL include field "error_type" for error logs (timeout, connection_error, auth_error, etc.)
15. THE System SHALL include field "error_code" for error logs (HTTP status code or custom code)
16. THE System SHALL include field "retry_attempt" for retry logs (1, 2, 3)
17. THE System SHALL include field "endpoint" for API request logs (URL path without query params)
18. THE System SHALL include field "method" for API request logs (GET, POST)
19. THE System SHALL include field "status_code" for API response logs (HTTP status)
20. THE System SHALL include field "response_code" for KoraPay-specific codes (00, Z0, 99)

**Log Levels and Usage:**

21. THE System SHALL use DEBUG level for: request/response bodies, detailed flow, variable values
22. THE System SHALL use INFO level for: API requests, API responses, payment confirmations, webhook deliveries
23. THE System SHALL use WARNING level for: mock mode operations, slow responses, retry attempts, rate limits
24. THE System SHALL use ERROR level for: API failures, authentication errors, validation errors, database errors
25. THE System SHALL use CRITICAL level for: startup failures, data corruption, security breaches, system down
26. THE System SHALL never log sensitive data at any level: API keys, secrets, passwords, full credit card numbers
27. THE System SHALL mask sensitive data in logs: email (show first 3 chars + @domain), phone (show last 4 digits)
28. THE System SHALL truncate long strings in logs to 200 characters with "..." indicator
29. THE System SHALL log stack traces only at DEBUG and ERROR levels
30. THE System SHALL log full exception details at ERROR level for debugging

**Log Rotation and Management:**

31. THE System SHALL implement log rotation using Python logging.handlers.RotatingFileHandler
32. THE System SHALL set maxBytes=104857600 (100MB) for each log file
33. THE System SHALL set backupCount=10 to keep 10 rotated log files
34. THE System SHALL compress rotated logs using gzip to save disk space
35. THE System SHALL create separate log files: logs/korapay.log, logs/korapay_security.log, logs/korapay_performance.log
36. THE System SHALL write all KoraPay operations to logs/korapay.log
37. THE System SHALL write security events to logs/korapay_security.log (signature failures, auth errors, blacklist events)
38. THE System SHALL write performance metrics to logs/korapay_performance.log (response times, slow queries)
39. THE System SHALL implement log file permissions: 640 (owner read/write, group read, no world access)
40. THE System SHALL implement log directory permissions: 750 (owner rwx, group rx, no world access)
41. THE System SHALL clean up logs older than 90 days using scheduled task
42. THE System SHALL document log retention policy in docs/LOGGING.md

**Log Analysis and Searching:**

43. THE System SHALL implement grep-friendly log format for easy searching
44. THE System SHALL document log search commands in docs/LOGGING.md:
    - Find all errors: grep '"level":"ERROR"' logs/korapay.log
    - Find transaction: grep '"tx_ref":"ONEPAY-ABC123"' logs/korapay.log
    - Find slow requests: grep '"duration_ms":[5-9][0-9][0-9][0-9]' logs/korapay.log
    - Find auth failures: grep '"error_type":"auth_error"' logs/korapay.log
45. THE System SHALL implement log aggregation script scripts/analyze_korapay_logs.py
46. THE Log_Analyzer SHALL parse JSON logs and generate statistics
47. THE Log_Analyzer SHALL calculate success rate, average response time, error breakdown
48. THE Log_Analyzer SHALL identify top errors by frequency
49. THE Log_Analyzer SHALL identify slowest operations by duration
50. THE Log_Analyzer SHALL generate daily log summary report
51. THE Log_Analyzer SHALL export report to reports/korapay_log_summary_YYYYMMDD.json
52. THE System SHALL document log analysis procedures in docs/LOGGING.md


### Requirement 44: Implement Detailed Incident Response and Recovery Procedures

**User Story:** As an on-call engineer, I want detailed incident response procedures for KoraPay integration failures, so that I can resolve issues quickly and minimize downtime.

#### Acceptance Criteria

**Incident Detection:**

1. THE System SHALL detect incident when korapay_api_success_rate < 80% for 5 minutes
2. THE System SHALL detect incident when korapay_consecutive_failures > 10
3. THE System SHALL detect incident when korapay_api_status = "down" for 5 minutes
4. THE System SHALL detect incident when webhook_signature_failures > 10 in 10 minutes
5. THE System SHALL detect incident when no successful API calls in last 10 minutes
6. THE System SHALL log CRITICAL "INCIDENT DETECTED | type={type} severity={severity}" when incident detected
7. THE System SHALL send alert email to on-call engineer with incident details
8. THE System SHALL send alert to monitoring system (PagerDuty, Opsgenie, etc.)
9. THE System SHALL create incident record in database with: id, type, severity, detected_at, resolved_at, resolution_notes
10. THE System SHALL assign incident ID for tracking and communication

**Incident Response Runbook:**

11. THE Documentation SHALL create file docs/KORAPAY_INCIDENT_RUNBOOK.md with response procedures
12. THE Runbook SHALL document incident "KoraPay API Down" with steps:
    - Check KoraPay status page: https://status.korapay.com
    - Check application logs: tail -f logs/korapay.log | grep ERROR
    - Check health endpoint: curl https://domain.com/health | jq .korapay_api_status
    - Verify network connectivity: ping api.korapay.com
    - Check DNS resolution: nslookup api.korapay.com
    - Contact KoraPay support if API is down
    - Enable maintenance mode if outage > 30 minutes
    - Communicate status to merchants via email
13. THE Runbook SHALL document incident "Authentication Failures" with steps:
    - Verify KORAPAY_SECRET_KEY in .env file
    - Check API key is active in KoraPay dashboard
    - Verify API key has not expired
    - Check API key permissions in dashboard
    - Regenerate API key if compromised
    - Update .env and restart application
14. THE Runbook SHALL document incident "Webhook Signature Failures" with steps:
    - Verify KORAPAY_WEBHOOK_SECRET in .env file
    - Check webhook secret in KoraPay dashboard matches
    - Test signature computation manually
    - Review webhook payload structure
    - Check for payload tampering or MITM attack
    - Regenerate webhook secret if compromised
15. THE Runbook SHALL document incident "High Error Rate" with steps:
    - Check recent code deployments
    - Review error logs for patterns
    - Check database connectivity and performance
    - Verify configuration is correct
    - Check for rate limiting issues
    - Consider rollback if recent deployment
16. THE Runbook SHALL document incident "Payment Confirmations Not Working" with steps:
    - Check transfer status polling is working
    - Verify webhook endpoint is accessible
    - Check webhook signature verification
    - Review transaction status in database
    - Query KoraPay API directly for transaction
    - Check for database lock issues
17. THE Runbook SHALL include escalation matrix: L1 (on-call engineer) -> L2 (senior engineer) -> L3 (CTO)
18. THE Runbook SHALL include escalation timeframes: L1 (30 min) -> L2 (1 hour) -> L3 (2 hours)
19. THE Runbook SHALL include communication templates for merchant notifications
20. THE Runbook SHALL include post-incident review template


### Requirement 45: Implement Detailed Data Validation and Sanitization

**User Story:** As a security engineer, I want comprehensive input validation and sanitization for all data sent to KoraPay, so that injection attacks and data corruption are prevented.

#### Acceptance Criteria

**Transaction Reference Validation:**

1. THE System SHALL validate transaction_reference matches pattern ^ONEPAY-[A-F0-9]{16}$
2. THE System SHALL validate transaction_reference length is exactly 23 characters
3. THE System SHALL validate transaction_reference contains only uppercase letters, digits, and hyphens
4. THE System SHALL reject transaction_reference with lowercase letters
5. THE System SHALL reject transaction_reference with special characters (except hyphen)
6. THE System SHALL reject transaction_reference with spaces
7. THE System SHALL reject transaction_reference with null bytes
8. THE System SHALL reject transaction_reference with SQL injection patterns (', --, /*, etc.)
9. THE System SHALL reject transaction_reference with path traversal patterns (../, ..\)
10. THE System SHALL reject transaction_reference with command injection patterns (;, |, &, $, `)

**Amount Validation:**

11. THE System SHALL validate amount is Decimal type (not float or int)
12. THE System SHALL validate amount has maximum 2 decimal places
13. THE System SHALL validate amount is positive (> 0)
14. THE System SHALL validate amount is at least ₦1.00 (100 kobo)
15. THE System SHALL validate amount does not exceed ₦999,999,999.99
16. THE System SHALL reject amount with more than 2 decimal places
17. THE System SHALL reject negative amounts
18. THE System SHALL reject zero amounts
19. THE System SHALL reject amounts with invalid characters
20. THE System SHALL reject amounts that would overflow integer conversion
21. THE System SHALL round amounts to 2 decimal places using ROUND_HALF_UP
22. THE System SHALL validate amount precision does not exceed 12 digits total
23. THE System SHALL convert amount to integer Naira for KoraPay (no kobo conversion)
24. THE System SHALL validate converted amount is between 100 and 999999999

**Customer Data Validation:**

25. THE System SHALL validate customer_email matches pattern ^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$
26. THE System SHALL validate customer_email length does not exceed 255 characters
27. THE System SHALL reject customer_email with spaces
28. THE System SHALL reject customer_email with multiple @ symbols
29. THE System SHALL reject customer_email with invalid TLD
30. THE System SHALL sanitize customer_email using html.escape() before storage
31. THE System SHALL validate customer_name length is between 2 and 100 characters
32. THE System SHALL reject customer_name with only whitespace
33. THE System SHALL reject customer_name with null bytes
34. THE System SHALL reject customer_name with control characters (except newline/tab)
35. THE System SHALL sanitize customer_name using html.escape() before sending to KoraPay
36. THE System SHALL validate customer_phone matches pattern ^\+?[0-9\s\-\(\)]{7,20}$
37. THE System SHALL reject customer_phone with letters
38. THE System SHALL reject customer_phone with special characters (except +, -, (, ), space)
39. THE System SHALL sanitize customer_phone by removing all non-digit characters except leading +
40. THE System SHALL validate sanitized phone has 7-15 digits

**Description and Narration Validation:**

41. THE System SHALL validate description length does not exceed 255 characters
42. THE System SHALL reject description with null bytes
43. THE System SHALL reject description with control characters (except newline/tab)
44. THE System SHALL sanitize description using html.escape() before storage
45. THE System SHALL strip leading and trailing whitespace from description
46. THE System SHALL validate narration length does not exceed 255 characters
47. THE System SHALL sanitize narration using html.escape() before sending to KoraPay
48. THE System SHALL reject narration with SQL injection patterns
49. THE System SHALL reject narration with XSS patterns (<script>, javascript:, onerror=)
50. THE System SHALL validate account_name length is between 3 and 100 characters
51. THE System SHALL sanitize account_name using html.escape()
52. THE System SHALL reject account_name with only whitespace

**URL Validation:**

53. THE System SHALL validate return_url using validate_return_url() function
54. THE System SHALL validate return_url length does not exceed 500 characters
55. THE System SHALL validate return_url starts with https:// in production
56. THE System SHALL allow return_url starting with / for relative paths
57. THE System SHALL reject return_url with javascript: scheme
58. THE System SHALL reject return_url with data: scheme
59. THE System SHALL reject return_url with file: scheme
60. THE System SHALL reject return_url pointing to localhost or private IPs
61. THE System SHALL validate webhook_url using validate_webhook_url() function
62. THE System SHALL validate webhook_url is absolute HTTPS URL (no relative paths)
63. THE System SHALL validate webhook_url does not contain credentials (username:password@)
64. THE System SHALL validate webhook_url does not contain fragments (#anchor)
65. THE System SHALL test webhook_url accessibility before saving (optional HEAD request)

**Metadata Validation:**

66. THE System SHALL validate metadata is dict type
67. THE System SHALL validate metadata has maximum 5 fields
68. THE System SHALL validate each metadata field name length <= 20 characters
69. THE System SHALL validate each metadata field name contains only alphanumeric and underscore
70. THE System SHALL validate each metadata value is string, number, or boolean (not nested objects)
71. THE System SHALL validate each metadata value length <= 100 characters if string
72. THE System SHALL reject metadata with reserved field names (internal, system, korapay)
73. THE System SHALL sanitize metadata values using html.escape() for strings
74. THE System SHALL serialize metadata to JSON before sending to KoraPay
75. THE System SHALL validate serialized metadata size does not exceed 1KB


### Requirement 46: Implement Detailed Backward Compatibility and Migration Path

**User Story:** As a product manager, I want the migration to be transparent to merchants and customers, so that no retraining or workflow changes are required.

#### Acceptance Criteria

**API Response Format Compatibility:**

1. THE System SHALL maintain existing API response format for /api/payments/create endpoint
2. THE System SHALL maintain existing API response format for /api/payments/transfer-status/{tx_ref} endpoint
3. THE System SHALL maintain existing API response format for /api/payments/preview/{tx_ref} endpoint
4. THE System SHALL return virtual account details in same format as Quickteller integration
5. THE System SHALL map KoraPay bank_name to existing virtual_bank_name field
6. THE System SHALL map KoraPay account_number to existing virtual_account_number field
7. THE System SHALL map KoraPay account_name to existing virtual_account_name field
8. THE System SHALL map KoraPay status codes to Quickteller-compatible codes (00, Z0, 99)
9. THE System SHALL maintain existing error response format: {"error": "message", "code": "ERROR_CODE"}
10. THE System SHALL maintain existing success response format: {"success": true, "tx_ref": "ref", ...}

**Database Schema Compatibility:**

11. THE System SHALL NOT rename any existing database columns
12. THE System SHALL NOT change data types of existing columns
13. THE System SHALL NOT remove any existing columns
14. THE System SHALL add new columns as nullable to support existing records
15. THE System SHALL provide default values for new columns when querying old records
16. THE System SHALL maintain existing foreign key relationships
17. THE System SHALL maintain existing database indexes
18. THE System SHALL maintain existing unique constraints
19. THE System SHALL support querying transactions created before migration
20. THE System SHALL display pre-migration transactions correctly in UI

**UI/UX Compatibility:**

21. THE System SHALL maintain existing payment link URL format: /pay/{tx_ref}
22. THE System SHALL maintain existing verify page layout and styling
23. THE System SHALL maintain existing dashboard layout and navigation
24. THE System SHALL maintain existing transaction history table columns
25. THE System SHALL maintain existing CSV export format and columns
26. THE System SHALL maintain existing QR code display and functionality
27. THE System SHALL maintain existing email templates and content
28. THE System SHALL maintain existing error messages shown to users
29. THE System SHALL maintain existing success messages shown to users
30. THE System SHALL maintain existing loading indicators and progress messages


### Requirement 47: Implement Detailed Timeout and Retry Configuration

**User Story:** As a system administrator, I want configurable timeout and retry settings, so that I can tune the integration for optimal reliability and performance.

#### Acceptance Criteria

**Timeout Configuration:**

1. THE System SHALL use connection timeout of 10 seconds for establishing TCP connection to KoraPay
2. THE System SHALL use read timeout of 30 seconds for receiving response from KoraPay
3. THE System SHALL configure timeouts as tuple (connect_timeout, read_timeout) in requests
4. THE System SHALL make timeouts configurable via KORAPAY_CONNECT_TIMEOUT_SECONDS environment variable
5. THE System SHALL make timeouts configurable via KORAPAY_READ_TIMEOUT_SECONDS environment variable
6. THE System SHALL validate timeout values are positive integers
7. THE System SHALL validate connect_timeout is less than read_timeout
8. THE System SHALL log "KoraPay timeouts configured | connect={connect}s read={read}s" at startup
9. WHEN timeout occurs, THE System SHALL log "KoraPay API timeout | endpoint={endpoint} connect_timeout={ct}s read_timeout={rt}s"
10. THE System SHALL include timeout values in error messages for debugging

**Retry Configuration:**

11. THE System SHALL use maximum 3 retry attempts for transient failures
12. THE System SHALL make max retries configurable via KORAPAY_MAX_RETRIES environment variable
13. THE System SHALL validate KORAPAY_MAX_RETRIES is between 0 and 10
14. THE System SHALL use exponential backoff with base 2: delays are 1s, 2s, 4s
15. THE System SHALL add random jitter between 0-500ms to each retry delay
16. THE System SHALL make retry delays configurable via KORAPAY_RETRY_BASE_DELAY_SECONDS
17. THE System SHALL calculate retry delay as: base_delay * (2 ** (attempt - 1)) + random(0, 0.5)
18. THE System SHALL log "Retry configuration | max_retries={max} base_delay={base}s jitter=0-500ms" at startup
19. THE System SHALL include retry attempt number in all retry logs
20. THE System SHALL include total elapsed time in final retry failure log

**Circuit Breaker Configuration:**

21. THE System SHALL implement circuit breaker pattern to prevent cascading failures
22. THE System SHALL configure circuit breaker threshold: 10 consecutive failures opens circuit
23. THE System SHALL configure circuit breaker timeout: 60 seconds before attempting recovery
24. THE System SHALL configure circuit breaker recovery: 1 successful request closes circuit
25. WHEN circuit opens, THE System SHALL log CRITICAL "Circuit breaker OPEN | consecutive_failures={count}"
26. WHEN circuit is open, THE System SHALL return error immediately without calling KoraPay
27. WHEN circuit is open, THE System SHALL return error "Payment provider temporarily unavailable (circuit breaker active)"
28. WHEN circuit timeout expires, THE System SHALL attempt one test request (half-open state)
29. WHEN test request succeeds, THE System SHALL close circuit and log "Circuit breaker CLOSED"
30. WHEN test request fails, THE System SHALL keep circuit open and reset timeout
31. THE System SHALL make circuit breaker configurable via KORAPAY_CIRCUIT_BREAKER_ENABLED (default true)
32. THE System SHALL make failure threshold configurable via KORAPAY_CIRCUIT_BREAKER_THRESHOLD (default 10)
33. THE System SHALL make recovery timeout configurable via KORAPAY_CIRCUIT_BREAKER_TIMEOUT_SECONDS (default 60)
34. THE System SHALL expose circuit breaker state in health check endpoint
35. THE System SHALL include field "korapay_circuit_breaker_state" with values: closed, open, half_open


### Requirement 48: Implement Comprehensive Edge Case Handling

**User Story:** As a QA engineer, I want comprehensive edge case handling for unusual scenarios, so that the system behaves correctly in all situations.

#### Acceptance Criteria

**Edge Case: Duplicate Transaction References:**

1. WHEN creating virtual account with duplicate reference, THE System SHALL check database for existing transaction
2. WHEN existing transaction found with same reference, THE System SHALL return existing virtual account details (idempotent)
3. WHEN existing transaction found, THE System SHALL NOT call KoraPay API again
4. WHEN existing transaction found, THE System SHALL log "Duplicate reference detected, returning cached result | ref={ref}"
5. WHEN KoraPay returns 409 Conflict for duplicate reference, THE System SHALL query transaction and return cached result
6. THE System SHALL validate idempotency across application restarts (persistent storage)

**Edge Case: Virtual Account Expiry:**

7. WHEN virtual account expires before payment, THE System SHALL update transaction status to EXPIRED
8. WHEN polling expired transaction, THE System SHALL return {"success": false, "status": "expired"}
9. WHEN polling expired transaction, THE System SHALL NOT call KoraPay API
10. THE System SHALL implement background job to mark expired transactions every 5 minutes
11. THE System SHALL query transactions with status PENDING and expires_at < now
12. THE System SHALL batch update expired transactions (max 100 per batch)
13. THE System SHALL log "Expired transactions marked | count={count}" after batch update
14. THE System SHALL sync invoice status to EXPIRED for expired transactions

**Edge Case: Concurrent Payment Confirmations:**

15. WHEN two polling requests confirm same transaction simultaneously, THE System SHALL use optimistic locking
16. THE System SHALL query transaction with with_for_update() to acquire row lock
17. THE System SHALL check transfer_confirmed flag after acquiring lock
18. WHEN already confirmed by another request, THE System SHALL return success without duplicate processing
19. WHEN not yet confirmed, THE System SHALL update status and process confirmation
20. THE System SHALL commit transaction atomically to prevent partial updates
21. THE System SHALL test concurrent confirmations with 10 simultaneous requests
22. THE System SHALL verify only one confirmation succeeds and others return idempotent response
23. THE System SHALL verify no duplicate webhooks are sent
24. THE System SHALL verify no duplicate emails are sent

**Edge Case: Webhook Delivery Failures:**

25. WHEN webhook delivery fails with timeout, THE System SHALL retry after 1 minute
26. WHEN webhook delivery fails with connection error, THE System SHALL retry after 2 minutes
27. WHEN webhook delivery fails with 5xx error, THE System SHALL retry after 5 minutes
28. WHEN webhook delivery fails 3 times, THE System SHALL mark as permanently failed
29. WHEN webhook permanently failed, THE System SHALL log ERROR "Webhook delivery failed permanently | ref={ref} url={url}"
30. WHEN webhook permanently failed, THE System SHALL send alert email to merchant
31. THE System SHALL implement background job to retry failed webhooks every 5 minutes
32. THE System SHALL query transactions with webhook_delivered=false and webhook_attempts < 3
33. THE System SHALL batch process failed webhooks (max 20 per batch)
34. THE System SHALL respect webhook rate limits during retry processing

**Edge Case: Amount Precision and Rounding:**

35. WHEN amount has more than 2 decimal places, THE System SHALL round using ROUND_HALF_UP
36. WHEN amount is ₦1500.505, THE System SHALL round to ₦1500.51
37. WHEN amount is ₦1500.504, THE System SHALL round to ₦1500.50
38. THE System SHALL log WARNING "Amount rounded | original={original} rounded={rounded}" when rounding occurs
39. THE System SHALL validate rounded amount still meets minimum (₦1.00)
40. THE System SHALL validate rounded amount still meets maximum (₦999,999,999.99)

**Edge Case: Network Interruptions:**

41. WHEN network connection drops during API request, THE System SHALL catch ConnectionError
42. WHEN network connection drops, THE System SHALL retry with exponential backoff
43. WHEN network restored, THE System SHALL resume normal operation
44. THE System SHALL not lose transaction state during network interruptions
45. THE System SHALL persist transaction status before making API calls
46. THE System SHALL implement request idempotency to handle duplicate requests after network recovery


### Requirement 49: Implement Detailed Property-Based Testing Requirements

**User Story:** As a developer, I want property-based tests that verify correctness properties hold for all inputs, so that edge cases are automatically discovered.

#### Acceptance Criteria

**Round-Trip Properties for Parser/Pretty-Printer:**

1. THE Test_Suite SHALL implement property test: FOR ALL valid VirtualAccount objects, parse(format(account)) == account
2. THE Test_Suite SHALL implement property test: FOR ALL valid TransferStatus objects, parse(format(status)) == status
3. THE Test_Suite SHALL implement property test: FOR ALL valid WebhookEvent objects, parse(format(event)) == event
4. THE Test_Suite SHALL use hypothesis library for property-based testing
5. THE Test_Suite SHALL generate random VirtualAccount objects with valid field values
6. THE Test_Suite SHALL generate random amounts between ₦100 and ₦999,999,999
7. THE Test_Suite SHALL generate random transaction references matching ONEPAY-[A-F0-9]{16} pattern
8. THE Test_Suite SHALL generate random bank names from list: wema, sterling, providus
9. THE Test_Suite SHALL generate random account numbers as 10-digit strings
10. THE Test_Suite SHALL run 100 test cases per property test
11. THE Test_Suite SHALL shrink failing examples to minimal counterexample
12. THE Test_Suite SHALL save failing examples for regression testing

**Invariant Properties:**

13. THE Test_Suite SHALL implement property test: FOR ALL transactions, amount > 0 (positive amount invariant)
14. THE Test_Suite SHALL implement property test: FOR ALL transactions, created_at <= verified_at when verified (timestamp ordering invariant)
15. THE Test_Suite SHALL implement property test: FOR ALL confirmed transactions, transfer_confirmed == true AND status == VERIFIED (consistency invariant)
16. THE Test_Suite SHALL implement property test: FOR ALL transactions, len(tx_ref) == 23 (reference length invariant)
17. THE Test_Suite SHALL implement property test: FOR ALL mock accounts, account_number is deterministic from tx_ref (determinism invariant)

**Metamorphic Properties:**

18. THE Test_Suite SHALL implement property test: Creating virtual account twice with same reference returns same account_number
19. THE Test_Suite SHALL implement property test: Polling status N times then once more returns same result as polling N+1 times
20. THE Test_Suite SHALL implement property test: Processing webhook twice produces same database state as processing once (idempotence)
21. THE Test_Suite SHALL implement property test: Amount in response <= amount in request + reasonable fee (fee sanity check)
22. THE Test_Suite SHALL implement property test: Mock poll count after N polls == min(N, MOCK_CONFIRM_AFTER)


### Requirement 50: Implement Detailed Compliance and Audit Requirements

**User Story:** As a compliance officer, I want comprehensive audit logging and compliance controls, so that the system meets regulatory requirements for financial transactions.

#### Acceptance Criteria

**Audit Logging Requirements:**

1. THE System SHALL log audit event "korapay.virtual_account_created" with fields: user_id, tx_ref, amount, currency, account_number, bank_name, timestamp
2. THE System SHALL log audit event "korapay.payment_confirmed" with fields: user_id, tx_ref, amount, confirmation_method (poll/webhook), verified_at, provider_fee
3. THE System SHALL log audit event "korapay.payment_failed" with fields: user_id, tx_ref, amount, failure_reason, failed_at
4. THE System SHALL log audit event "korapay.refund_initiated" with fields: user_id, tx_ref, refund_reference, refund_amount, reason, initiated_at
5. THE System SHALL log audit event "korapay.refund_completed" with fields: user_id, tx_ref, refund_reference, status, processed_at
6. THE System SHALL log audit event "korapay.webhook_received" with fields: event_type, tx_ref, source_ip, signature_valid, processed_at
7. THE System SHALL log audit event "korapay.webhook_signature_failed" with fields: tx_ref, source_ip, signature_received, timestamp
8. THE System SHALL log audit event "korapay.api_error" with fields: endpoint, error_type, error_code, tx_ref, timestamp
9. THE System SHALL log audit event "korapay.config_changed" with fields: user_id, setting_name, old_value, new_value, changed_at
10. THE System SHALL store all audit events in audit_logs table with retention period 7 years (financial compliance)
11. THE System SHALL implement audit log immutability (no updates or deletes allowed)
12. THE System SHALL implement audit log integrity using hash chain (each log entry includes hash of previous entry)
13. THE System SHALL validate audit log integrity on startup
14. WHEN audit log tampering detected, THE System SHALL log CRITICAL alert and abort startup
15. THE System SHALL export audit logs to secure external storage daily

**Compliance Controls:**

16. THE System SHALL implement PCI DSS compliance controls for payment data handling
17. THE System SHALL never store full credit card numbers (not applicable for bank transfers)
18. THE System SHALL never log full credit card numbers
19. THE System SHALL implement data retention policy: transaction data retained for 7 years
20. THE System SHALL implement data deletion procedure for GDPR compliance (customer data only, not financial records)
21. THE System SHALL implement data export procedure for GDPR data portability requests
22. THE System SHALL encrypt sensitive data at rest (API keys, webhook secrets)
23. THE System SHALL encrypt sensitive data in transit (HTTPS for all API calls)
24. THE System SHALL implement access controls: only authorized users can view transaction details
25. THE System SHALL implement audit trail for all data access (who viewed what when)
26. THE System SHALL implement data anonymization for analytics (remove PII)
27. THE System SHALL document compliance controls in docs/COMPLIANCE.md
28. THE System SHALL document data retention policy in docs/DATA_RETENTION.md
29. THE System SHALL document GDPR procedures in docs/GDPR_COMPLIANCE.md
30. THE System SHALL conduct annual compliance audit and document results


### Requirement 51: Implement Performance Monitoring and SLA Enforcement

**User Story:** As a platform engineer, I want real-time performance monitoring with automated SLA enforcement, so that performance degradation is detected and mitigated automatically.

#### Acceptance Criteria

**Performance Metrics Collection:**

1. THE System SHALL collect metric: api_request_duration_ms for all KoraPay API calls with percentiles (p50, p95, p99)
2. THE System SHALL collect metric: api_request_count with labels: endpoint, status_code, success/failure
3. THE System SHALL collect metric: api_error_rate as percentage of failed requests per minute
4. THE System SHALL collect metric: database_query_duration_ms for all queries with percentiles
5. THE System SHALL collect metric: webhook_delivery_duration_ms for all webhook deliveries
6. THE System SHALL collect metric: concurrent_confirmations_count tracking simultaneous confirmation attempts
7. THE System SHALL collect metric: connection_pool_utilization as percentage of active connections
8. THE System SHALL collect metric: memory_usage_mb tracking service memory consumption
9. THE System SHALL collect metric: cpu_usage_percent tracking service CPU utilization
10. THE System SHALL export metrics in Prometheus format at /metrics endpoint

**SLA Monitoring:**

11. THE System SHALL monitor SLA: virtual_account_creation_p95 < 2000ms
12. THE System SHALL monitor SLA: transfer_status_query_p95 < 1000ms
13. THE System SHALL monitor SLA: webhook_processing_p95 < 500ms
14. THE System SHALL monitor SLA: database_query_p95 < 100ms
15. THE System SHALL monitor SLA: api_success_rate > 99.5%
16. WHEN SLA violated for 5 consecutive minutes, THE System SHALL trigger alert to on-call engineer
17. WHEN SLA violated for 15 consecutive minutes, THE System SHALL trigger escalation to senior engineer
18. WHEN SLA violated for 30 consecutive minutes, THE System SHALL trigger incident response procedure

**Performance Degradation Detection:**

19. THE System SHALL detect performance degradation when p95 latency increases by 50% over 5-minute baseline
20. THE System SHALL detect performance degradation when error rate increases by 100% over 5-minute baseline
21. WHEN performance degradation detected, THE System SHALL log WARNING with metrics snapshot
22. WHEN performance degradation detected, THE System SHALL increase logging verbosity to DEBUG level
23. WHEN performance degradation detected, THE System SHALL collect diagnostic data (thread dumps, memory profiles)
24. THE System SHALL implement automatic recovery: restart connection pool when utilization > 90%
25. THE System SHALL implement automatic recovery: clear caches when memory usage > 80%

**Performance Testing Requirements:**

26. THE System SHALL support load testing with Apache Bench or Locust
27. THE System SHALL support stress testing up to 10x normal load
28. THE System SHALL support endurance testing for 24-hour continuous operation
29. THE System SHALL support spike testing with sudden 100x load increase
30. THE System SHALL document performance test procedures in docs/PERFORMANCE_TESTING.md


### Requirement 52: Implement Scalability and High Availability Architecture

**User Story:** As a platform architect, I want the system to scale horizontally and maintain high availability, so that it can handle growth and survive component failures.

#### Acceptance Criteria

**Horizontal Scaling:**

1. THE System SHALL support running multiple application instances behind a load balancer
2. THE System SHALL use database-backed session storage (not in-memory) for multi-instance deployments
3. THE System SHALL use database-backed rate limiting (not in-memory) for consistent limits across instances
4. THE System SHALL implement distributed locking using database advisory locks for critical sections
5. THE System SHALL avoid instance-specific state (all state in database or external cache)
6. THE System SHALL support graceful shutdown: finish processing current requests before terminating
7. THE System SHALL support rolling deployments: deploy new version without downtime
8. THE System SHALL support blue-green deployments: switch traffic between two environments
9. THE System SHALL implement health check endpoint for load balancer health probes
10. THE System SHALL return HTTP 503 during graceful shutdown to stop receiving new requests

**Database Scalability:**

11. THE System SHALL use connection pooling with max 20 connections per instance
12. THE System SHALL implement connection pool monitoring and alerting
13. THE System SHALL use read replicas for read-heavy queries (transaction history, reporting)
14. THE System SHALL use write-ahead logging (WAL) for PostgreSQL to improve write performance
15. THE System SHALL implement database query timeout: 5 seconds for all queries
16. THE System SHALL implement slow query logging: log queries > 1 second
17. THE System SHALL use database indexes on all foreign keys and frequently queried columns
18. THE System SHALL implement database partitioning for transactions table when > 10M rows
19. THE System SHALL implement archive strategy: move transactions > 2 years old to archive table
20. THE System SHALL support database backup and restore without downtime (hot backup)

**Caching Strategy:**

21. THE System SHALL implement Redis cache for user settings with 5-minute TTL
22. THE System SHALL implement Redis cache for KoraPay health status with 60-second TTL
23. THE System SHALL implement cache invalidation on configuration changes
24. THE System SHALL implement cache warming on application startup
25. THE System SHALL monitor cache hit rate (target: > 80%)
26. THE System SHALL implement cache fallback: query database if cache unavailable
27. THE System SHALL implement cache stampede prevention using lock-based cache warming
28. THE System SHALL use cache-aside pattern: check cache, query DB on miss, populate cache
29. THE System SHALL implement cache serialization using JSON or MessagePack
30. THE System SHALL implement cache key namespacing to prevent collisions

**High Availability:**

31. THE System SHALL support active-active deployment across multiple availability zones
32. THE System SHALL implement automatic failover when primary database unavailable
33. THE System SHALL implement circuit breaker to stop calling failed dependencies
34. THE System SHALL implement retry with exponential backoff for transient failures
35. THE System SHALL implement timeout for all external calls (KoraPay API, webhooks, email)
36. THE System SHALL implement bulkhead pattern: isolate KoraPay failures from other services
37. THE System SHALL implement graceful degradation: disable non-critical features during outages
38. THE System SHALL maintain core functionality (view transactions) during KoraPay outage
39. THE System SHALL implement health check with dependency status (database, KoraPay, email)
40. THE System SHALL support zero-downtime deployments using rolling updates


### Requirement 53: Implement CI/CD Pipeline and Deployment Automation

**User Story:** As a DevOps engineer, I want automated CI/CD pipelines with comprehensive quality gates, so that deployments are safe, repeatable, and auditable.

#### Acceptance Criteria

**Continuous Integration Pipeline:**

1. THE CI_Pipeline SHALL run on every commit to main branch and all pull requests
2. THE CI_Pipeline SHALL execute linting with ruff and fail on any errors
3. THE CI_Pipeline SHALL execute type checking with mypy and fail on any errors
4. THE CI_Pipeline SHALL execute security scanning with bandit and fail on high/critical issues
5. THE CI_Pipeline SHALL execute dependency vulnerability scanning with safety and fail on known CVEs
6. THE CI_Pipeline SHALL execute unit tests and fail if coverage < 95%
7. THE CI_Pipeline SHALL execute integration tests and fail if any test fails
8. THE CI_Pipeline SHALL execute property-based tests with 1000 iterations and fail if any property violated
9. THE CI_Pipeline SHALL execute security tests and fail if any security control bypassed
10. THE CI_Pipeline SHALL execute performance tests and fail if SLAs violated
11. THE CI_Pipeline SHALL build Docker image and push to container registry
12. THE CI_Pipeline SHALL tag Docker images with git commit SHA and semantic version
13. THE CI_Pipeline SHALL scan Docker image for vulnerabilities with Trivy
14. THE CI_Pipeline SHALL generate code coverage report and publish to coverage service
15. THE CI_Pipeline SHALL generate test report and publish as CI artifact

**Continuous Deployment Pipeline:**

16. THE CD_Pipeline SHALL deploy to staging environment automatically after CI passes on main branch
17. THE CD_Pipeline SHALL run smoke tests in staging environment
18. THE CD_Pipeline SHALL require manual approval for production deployment
19. THE CD_Pipeline SHALL create database backup before production deployment
20. THE CD_Pipeline SHALL run database migrations in production using Alembic
21. THE CD_Pipeline SHALL deploy application using rolling update strategy (zero downtime)
22. THE CD_Pipeline SHALL run post-deployment verification tests
23. THE CD_Pipeline SHALL monitor error rate for 15 minutes after deployment
24. THE CD_Pipeline SHALL automatically rollback if error rate > 5% after deployment
25. THE CD_Pipeline SHALL send deployment notification to Slack/email with deployment details

**Quality Gates:**

26. THE System SHALL enforce quality gate: all tests must pass before merge
27. THE System SHALL enforce quality gate: code coverage must be >= 95% before merge
28. THE System SHALL enforce quality gate: no high/critical security issues before merge
29. THE System SHALL enforce quality gate: no linting errors before merge
30. THE System SHALL enforce quality gate: code review approval required before merge
31. THE System SHALL enforce quality gate: all CI checks must pass before deployment
32. THE System SHALL enforce quality gate: staging tests must pass before production deployment
33. THE System SHALL enforce quality gate: manual approval required for production deployment
34. THE System SHALL enforce quality gate: database backup must succeed before deployment
35. THE System SHALL enforce quality gate: rollback procedure must be tested before deployment

**Deployment Artifacts:**

36. THE System SHALL generate deployment manifest with version, commit SHA, timestamp, deployer
37. THE System SHALL generate changelog from git commits since last deployment
38. THE System SHALL generate database migration plan showing SQL statements to execute
39. THE System SHALL generate rollback plan with exact steps to revert deployment
40. THE System SHALL archive deployment artifacts for audit trail (retain 2 years)


### Requirement 54: Implement Advanced Security Controls and Threat Mitigation

**User Story:** As a security architect, I want defense-in-depth security controls with threat detection and automated response, so that the system is resilient against attacks.

#### Acceptance Criteria

**Threat Detection:**

1. THE System SHALL detect brute force attacks: > 10 failed webhook signature verifications from same IP in 1 minute
2. THE System SHALL detect credential stuffing: > 20 failed authentication attempts from same IP in 5 minutes
3. THE System SHALL detect API abuse: > 100 requests from same IP in 1 minute across all endpoints
4. THE System SHALL detect SQL injection attempts: log and block requests with SQL patterns in parameters
5. THE System SHALL detect XSS attempts: log and sanitize requests with script tags or javascript: URLs
6. THE System SHALL detect SSRF attempts: log and block webhook URLs pointing to private IPs
7. THE System SHALL detect timing attacks: use constant-time comparison for all signature verifications
8. THE System SHALL detect replay attacks: reject webhooks with timestamps > 5 minutes old
9. THE System SHALL detect enumeration attacks: rate limit transaction reference guessing attempts
10. THE System SHALL detect DoS attacks: implement global rate limit of 1000 requests/minute

**Automated Threat Response:**

11. WHEN brute force attack detected, THE System SHALL block IP address for 1 hour
12. WHEN credential stuffing detected, THE System SHALL block IP address for 24 hours
13. WHEN API abuse detected, THE System SHALL rate limit IP to 10 requests/minute for 1 hour
14. WHEN SQL injection detected, THE System SHALL block request and log security incident
15. WHEN SSRF attempt detected, THE System SHALL blacklist webhook URL permanently
16. WHEN DoS attack detected, THE System SHALL enable aggressive rate limiting globally
17. THE System SHALL log all security incidents to security_incidents table
18. THE System SHALL send security alert email to security team for critical incidents
19. THE System SHALL send security alert to SIEM system for all incidents
20. THE System SHALL implement incident response playbook in docs/INCIDENT_RESPONSE.md

**Security Hardening:**

21. THE System SHALL implement Content Security Policy (CSP) headers on all HTML responses
22. THE System SHALL implement X-Frame-Options: DENY to prevent clickjacking
23. THE System SHALL implement X-Content-Type-Options: nosniff to prevent MIME sniffing
24. THE System SHALL implement Strict-Transport-Security header with max-age=31536000
25. THE System SHALL implement Referrer-Policy: strict-origin-when-cross-origin
26. THE System SHALL implement Permissions-Policy to disable unnecessary browser features
27. THE System SHALL disable server version disclosure in HTTP headers
28. THE System SHALL disable stack trace exposure in production error responses
29. THE System SHALL implement request size limits: max 1MB for all requests
30. THE System SHALL implement request timeout: max 30 seconds for all requests

**Penetration Testing:**

31. THE System SHALL conduct penetration testing before production deployment
32. THE System SHALL test for OWASP Top 10 vulnerabilities
33. THE System SHALL test for payment-specific vulnerabilities (amount manipulation, race conditions)
34. THE System SHALL test for API security vulnerabilities (authentication bypass, authorization flaws)
35. THE System SHALL test for webhook security vulnerabilities (signature bypass, replay attacks)
36. THE System SHALL document penetration test results in security-reports/
37. THE System SHALL remediate all critical/high findings before production deployment
38. THE System SHALL conduct annual penetration testing and document results
39. THE System SHALL implement bug bounty program for responsible disclosure
40. THE System SHALL document security testing procedures in docs/SECURITY_TESTING.md


### Requirement 55: Implement Chaos Engineering and Resilience Testing

**User Story:** As a reliability engineer, I want chaos engineering experiments to validate system resilience, so that failures are handled gracefully in production.

#### Acceptance Criteria

**Chaos Experiments:**

1. THE System SHALL support chaos experiment: kill random application instance during payment processing
2. THE System SHALL support chaos experiment: introduce 5-second latency to KoraPay API calls
3. THE System SHALL support chaos experiment: return 500 errors from KoraPay API for 50% of requests
4. THE System SHALL support chaos experiment: disconnect database for 10 seconds
5. THE System SHALL support chaos experiment: fill disk to 95% capacity
6. THE System SHALL support chaos experiment: exhaust database connection pool
7. THE System SHALL support chaos experiment: corrupt webhook signatures
8. THE System SHALL support chaos experiment: send duplicate webhooks simultaneously
9. THE System SHALL support chaos experiment: trigger 100 concurrent confirmations for same transaction
10. THE System SHALL support chaos experiment: simulate network partition between app and database

**Resilience Validation:**

11. WHEN application instance killed, THE System SHALL complete in-flight requests on other instances
12. WHEN KoraPay API slow, THE System SHALL timeout after 30 seconds and retry
13. WHEN KoraPay API returns errors, THE System SHALL retry 3 times then fail gracefully
14. WHEN database disconnected, THE System SHALL queue operations and retry after reconnection
15. WHEN disk full, THE System SHALL log critical alert and stop accepting new payments
16. WHEN connection pool exhausted, THE System SHALL queue requests and process when connections available
17. WHEN webhook signatures corrupted, THE System SHALL reject webhooks and log security incident
18. WHEN duplicate webhooks received, THE System SHALL process idempotently without data corruption
19. WHEN concurrent confirmations attempted, THE System SHALL use optimistic locking to prevent race conditions
20. WHEN network partition occurs, THE System SHALL detect and log partition event

**Failure Recovery:**

21. THE System SHALL recover automatically from transient failures within 60 seconds
22. THE System SHALL recover automatically from database connection loss within 30 seconds
23. THE System SHALL recover automatically from KoraPay API outage when service restored
24. THE System SHALL recover automatically from disk space issues when space freed
25. THE System SHALL recover automatically from memory pressure by clearing caches
26. THE System SHALL implement exponential backoff for all retry logic (max 60 seconds)
27. THE System SHALL implement jitter in retry delays to prevent thundering herd
28. THE System SHALL log all recovery attempts with success/failure status
29. THE System SHALL alert on-call engineer if recovery fails after 5 minutes
30. THE System SHALL document failure recovery procedures in docs/FAILURE_RECOVERY.md

**Chaos Testing Framework:**

31. THE System SHALL implement chaos testing framework using Chaos Toolkit or custom scripts
32. THE System SHALL implement chaos experiments as automated tests in tests/chaos/
33. THE System SHALL run chaos experiments in staging environment weekly
34. THE System SHALL document chaos experiment results and system behavior
35. THE System SHALL improve resilience based on chaos experiment findings
36. THE System SHALL implement GameDay exercises: simulate production incidents in staging
37. THE System SHALL conduct GameDay exercises quarterly with full team participation
38. THE System SHALL document GameDay procedures and runbooks in docs/GAMEDAY.md
39. THE System SHALL measure Mean Time To Recovery (MTTR) during GameDay exercises
40. THE System SHALL set MTTR target: < 15 minutes for critical incidents


### Requirement 56: Implement Observability and Distributed Tracing

**User Story:** As a platform engineer, I want distributed tracing and comprehensive observability, so that I can diagnose issues across service boundaries quickly.

#### Acceptance Criteria

**Distributed Tracing:**

1. THE System SHALL implement distributed tracing using OpenTelemetry or similar framework
2. THE System SHALL generate unique trace_id for each payment flow (creation → confirmation)
3. THE System SHALL propagate trace_id across all components (blueprints, services, database)
4. THE System SHALL include trace_id in all log messages for correlation
5. THE System SHALL include trace_id in KoraPay API requests via X-Request-ID header
6. THE System SHALL create span for each operation: create_payment_link, create_virtual_account, confirm_transfer, deliver_webhook
7. THE System SHALL record span duration, status (success/error), and attributes (tx_ref, amount, user_id)
8. THE System SHALL export traces to tracing backend (Jaeger, Zipkin, or cloud provider)
9. THE System SHALL implement trace sampling: 100% for errors, 10% for successful requests
10. THE System SHALL implement trace retention: 7 days for all traces, 30 days for error traces

**Structured Logging:**

11. THE System SHALL use structured logging with JSON format for all log messages
12. THE System SHALL include standard fields in all logs: timestamp, level, component, operation, trace_id, tx_ref
13. THE System SHALL include contextual fields: user_id, ip_address, request_id, duration_ms
14. THE System SHALL implement log aggregation using ELK stack, Loki, or cloud logging service
15. THE System SHALL implement log search and filtering by any field
16. THE System SHALL implement log alerting based on patterns (error rate, specific error messages)
17. THE System SHALL implement log retention: 30 days for INFO, 90 days for WARNING/ERROR, 1 year for CRITICAL
18. THE System SHALL implement log sampling for high-volume DEBUG logs (10% sampling)
19. THE System SHALL implement log redaction: mask PII and sensitive data automatically
20. THE System SHALL implement log correlation: link all logs for same payment flow

**Metrics and Dashboards:**

21. THE System SHALL implement Grafana dashboard for KoraPay integration metrics
22. THE Dashboard SHALL display real-time API request rate (requests/second)
23. THE Dashboard SHALL display real-time API error rate (errors/second)
24. THE Dashboard SHALL display API latency percentiles (p50, p95, p99) over time
25. THE Dashboard SHALL display success rate percentage over time
26. THE Dashboard SHALL display active payment flows (pending confirmations)
27. THE Dashboard SHALL display webhook delivery success rate
28. THE Dashboard SHALL display database connection pool utilization
29. THE Dashboard SHALL display cache hit rate percentage
30. THE Dashboard SHALL display circuit breaker state (closed/open/half-open)

**Alerting Rules:**

31. THE System SHALL alert when API error rate > 5% for 5 minutes (CRITICAL)
32. THE System SHALL alert when API p95 latency > 5 seconds for 5 minutes (WARNING)
33. THE System SHALL alert when webhook delivery failure rate > 10% for 5 minutes (WARNING)
34. THE System SHALL alert when database connection pool > 90% for 5 minutes (WARNING)
35. THE System SHALL alert when circuit breaker opens (CRITICAL)
36. THE System SHALL alert when disk space < 10% (CRITICAL)
37. THE System SHALL alert when memory usage > 80% for 10 minutes (WARNING)
38. THE System SHALL alert when no successful payments in 30 minutes during business hours (CRITICAL)
39. THE System SHALL implement alert deduplication: max 1 alert per issue per hour
40. THE System SHALL implement alert escalation: escalate to senior engineer if not acknowledged in 15 minutes


### Requirement 57: Implement Edge Case Handling and Boundary Conditions

**User Story:** As a developer, I want comprehensive edge case handling, so that the system behaves correctly under unusual conditions.

#### Acceptance Criteria

**Amount Edge Cases:**

1. THE System SHALL handle minimum amount: ₦1.00 (100 kobo) correctly
2. THE System SHALL handle maximum amount: ₦999,999,999.99 correctly
3. THE System SHALL handle amount with maximum precision: 2 decimal places
4. THE System SHALL reject amounts with > 2 decimal places by rounding using ROUND_HALF_UP
5. THE System SHALL reject negative amounts with validation error
6. THE System SHALL reject zero amounts with validation error
7. THE System SHALL reject amounts > ₦999,999,999.99 with validation error
8. THE System SHALL handle amounts with trailing zeros: ₦100.00 == ₦100.0 == ₦100
9. THE System SHALL handle amounts in scientific notation: 1.5e3 == ₦1500
10. THE System SHALL reject infinite amounts (Decimal('inf')) with validation error
11. THE System SHALL reject NaN amounts (Decimal('nan')) with validation error

**Transaction Reference Edge Cases:**

12. THE System SHALL handle transaction references with all uppercase hex digits
13. THE System SHALL handle transaction references with all lowercase hex digits (normalize to uppercase)
14. THE System SHALL reject transaction references with invalid characters (G-Z, special chars)
15. THE System SHALL reject transaction references shorter than 23 characters
16. THE System SHALL reject transaction references longer than 23 characters
17. THE System SHALL reject transaction references not starting with "ONEPAY-"
18. THE System SHALL handle transaction reference collision (extremely rare) by regenerating
19. THE System SHALL validate transaction reference uniqueness before database insert
20. THE System SHALL handle transaction reference with null bytes by rejecting

**Timestamp Edge Cases:**

21. THE System SHALL handle transactions created at exactly midnight UTC
22. THE System SHALL handle transactions expiring at exactly midnight UTC
23. THE System SHALL handle timezone conversions correctly (UTC storage, local display)
24. THE System SHALL handle daylight saving time transitions correctly
25. THE System SHALL handle leap seconds correctly (use UTC without leap seconds)
26. THE System SHALL handle year 2038 problem (use 64-bit timestamps)
27. THE System SHALL reject timestamps in the past for expiry
28. THE System SHALL reject timestamps > 1 year in future for expiry
29. THE System SHALL handle concurrent confirmations with same timestamp (use microsecond precision)
30. THE System SHALL handle webhook timestamps with different timezone formats (normalize to UTC)

**String Edge Cases:**

31. THE System SHALL handle customer names with unicode characters (emoji, accents, CJK)
32. THE System SHALL handle customer names with maximum length (100 characters)
33. THE System SHALL handle customer names with minimum length (2 characters)
34. THE System SHALL reject customer names with only whitespace
35. THE System SHALL handle descriptions with maximum length (255 characters)
36. THE System SHALL handle descriptions with unicode characters
37. THE System SHALL handle email addresses with maximum length (255 characters)
38. THE System SHALL handle email addresses with plus addressing (user+tag@domain.com)
39. THE System SHALL handle email addresses with subdomains (user@mail.example.com)
40. THE System SHALL reject email addresses with invalid format

**Concurrency Edge Cases:**

41. THE System SHALL handle 1000 concurrent payment link creations from same user
42. THE System SHALL handle 100 concurrent status polls for same transaction
43. THE System SHALL handle 50 concurrent webhook deliveries for same transaction
44. THE System SHALL handle database deadlocks by retrying transaction
45. THE System SHALL handle optimistic locking failures by retrying with fresh data
46. THE System SHALL handle race condition: two requests confirm same transaction simultaneously
47. THE System SHALL handle race condition: payment confirmed while expiry check running
48. THE System SHALL handle race condition: webhook received while polling confirmation
49. THE System SHALL prevent double-spending: transaction can only be confirmed once
50. THE System SHALL prevent duplicate webhooks: idempotent webhook processing

**Network Edge Cases:**

51. THE System SHALL handle KoraPay API returning empty response body
52. THE System SHALL handle KoraPay API returning malformed JSON
53. THE System SHALL handle KoraPay API returning unexpected status code (e.g., 418)
54. THE System SHALL handle KoraPay API connection timeout during request
55. THE System SHALL handle KoraPay API connection timeout during response
56. THE System SHALL handle KoraPay API connection reset by peer
57. THE System SHALL handle KoraPay API SSL certificate expiry
58. THE System SHALL handle KoraPay API DNS resolution failure
59. THE System SHALL handle KoraPay API returning redirect (reject with error)
60. THE System SHALL handle partial response from KoraPay API (connection closed mid-response)


### Requirement 58: Implement Advanced Deployment Strategies and Rollback Procedures

**User Story:** As a DevOps engineer, I want sophisticated deployment strategies with automated rollback, so that deployments are safe and reversible.

#### Acceptance Criteria

**Deployment Strategies:**

1. THE System SHALL support canary deployment: deploy to 5% of instances first
2. THE System SHALL monitor canary instances for 15 minutes before full rollout
3. THE System SHALL automatically rollback canary if error rate > 5%
4. THE System SHALL support blue-green deployment: maintain two identical environments
5. THE System SHALL switch traffic from blue to green using load balancer configuration
6. THE System SHALL keep blue environment running for 24 hours after green deployment (quick rollback)
7. THE System SHALL support feature flags: enable/disable KoraPay integration per merchant
8. THE System SHALL support gradual rollout: enable for 10%, 25%, 50%, 100% of merchants
9. THE System SHALL support A/B testing: compare KoraPay vs Quickteller performance
10. THE System SHALL support shadow mode: send requests to both providers, use Quickteller results

**Automated Rollback:**

11. THE System SHALL automatically rollback if deployment health check fails
12. THE System SHALL automatically rollback if error rate > 10% in first 5 minutes
13. THE System SHALL automatically rollback if p95 latency > 10 seconds in first 5 minutes
14. THE System SHALL automatically rollback if database migration fails
15. THE System SHALL automatically rollback if smoke tests fail after deployment
16. THE System SHALL automatically rollback if critical dependency unavailable
17. THE System SHALL execute rollback within 2 minutes of trigger
18. THE System SHALL verify rollback success by running health checks
19. THE System SHALL notify team of automatic rollback with reason and metrics
20. THE System SHALL create incident ticket for automatic rollback for investigation

**Manual Rollback Procedures:**

21. THE System SHALL document manual rollback procedure in docs/ROLLBACK.md
22. THE System SHALL provide rollback script: scripts/rollback_to_quickteller.py
23. THE Rollback_Script SHALL restore database from pre-deployment backup
24. THE Rollback_Script SHALL revert code to pre-deployment git tag
25. THE Rollback_Script SHALL restart application with Quickteller configuration
26. THE Rollback_Script SHALL verify Quickteller functionality with smoke tests
27. THE Rollback_Script SHALL update load balancer to route to rolled-back instances
28. THE Rollback_Script SHALL log rollback event to audit log
29. THE Rollback_Script SHALL send rollback notification to team
30. THE Rollback_Script SHALL complete rollback within 5 minutes

**Deployment Verification:**

31. THE System SHALL run smoke test: create payment link in production
32. THE System SHALL run smoke test: poll status for test transaction
33. THE System SHALL run smoke test: verify health check returns healthy
34. THE System SHALL run smoke test: verify database connectivity
35. THE System SHALL run smoke test: verify KoraPay API connectivity
36. THE System SHALL run smoke test: verify webhook signature verification
37. THE System SHALL run smoke test: verify email sending
38. THE System SHALL run smoke test: verify QR code generation
39. THE System SHALL run smoke test: verify invoice generation
40. THE System SHALL fail deployment if any smoke test fails

**Deployment Documentation:**

41. THE System SHALL document deployment checklist in docs/DEPLOYMENT_CHECKLIST.md
42. THE System SHALL document pre-deployment verification steps
43. THE System SHALL document deployment execution steps
44. THE System SHALL document post-deployment verification steps
45. THE System SHALL document rollback decision criteria
46. THE System SHALL document rollback execution steps
47. THE System SHALL document communication plan (who to notify, when, how)
48. THE System SHALL document maintenance window procedures
49. THE System SHALL document emergency deployment procedures (hotfix)
50. THE System SHALL document deployment retrospective template


### Requirement 59: Implement Load Testing and Capacity Planning

**User Story:** As a performance engineer, I want comprehensive load testing with capacity planning, so that the system can handle expected and peak traffic.

#### Acceptance Criteria

**Load Testing Scenarios:**

1. THE System SHALL support load test: 100 concurrent users creating payment links
2. THE System SHALL support load test: 500 concurrent customers polling transfer status
3. THE System SHALL support load test: 1000 concurrent webhook deliveries
4. THE System SHALL support load test: sustained load of 50 requests/second for 1 hour
5. THE System SHALL support load test: spike load of 500 requests/second for 5 minutes
6. THE System SHALL support load test: gradual ramp-up from 10 to 200 requests/second over 30 minutes
7. THE System SHALL support load test: stress test at 10x normal load until failure
8. THE System SHALL support load test: endurance test at normal load for 24 hours
9. THE System SHALL support load test: mixed workload (50% create, 40% poll, 10% webhook)
10. THE System SHALL document load test procedures in docs/LOAD_TESTING.md

**Performance Benchmarks:**

11. THE System SHALL achieve throughput: 100 payment links created per minute per instance
12. THE System SHALL achieve throughput: 500 status polls per minute per instance
13. THE System SHALL achieve throughput: 200 webhooks processed per minute per instance
14. THE System SHALL achieve latency: virtual account creation < 2s (p95)
15. THE System SHALL achieve latency: transfer status query < 1s (p95)
16. THE System SHALL achieve latency: webhook processing < 500ms (p95)
17. THE System SHALL achieve latency: database query < 100ms (p95)
18. THE System SHALL achieve success rate: > 99.5% for all operations
19. THE System SHALL achieve availability: 99.9% uptime (43 minutes downtime/month)
20. THE System SHALL document performance benchmarks in docs/PERFORMANCE_BENCHMARKS.md

**Capacity Planning:**

21. THE System SHALL calculate capacity: max concurrent users per instance
22. THE System SHALL calculate capacity: max requests per second per instance
23. THE System SHALL calculate capacity: max database connections per instance
24. THE System SHALL calculate capacity: max memory usage per instance
25. THE System SHALL calculate capacity: max CPU usage per instance
26. THE System SHALL calculate capacity: max disk I/O per instance
27. THE System SHALL calculate capacity: max network bandwidth per instance
28. THE System SHALL calculate scaling factor: instances needed for 2x, 5x, 10x traffic
29. THE System SHALL document capacity planning in docs/CAPACITY_PLANNING.md
30. THE System SHALL review capacity quarterly and adjust infrastructure

**Resource Limits:**

31. THE System SHALL limit memory usage: max 512MB per instance
32. THE System SHALL limit CPU usage: max 80% sustained per instance
33. THE System SHALL limit database connections: max 20 per instance
34. THE System SHALL limit open file descriptors: max 1024 per instance
35. THE System SHALL limit thread count: max 50 threads per instance
36. THE System SHALL limit request queue: max 100 pending requests per instance
37. THE System SHALL limit response size: max 10MB per response
38. THE System SHALL limit log file size: max 100MB per file
39. THE System SHALL limit cache size: max 100MB per instance
40. THE System SHALL monitor resource usage and alert when limits approached


### Requirement 60: Implement Disaster Recovery and Business Continuity

**User Story:** As a business continuity manager, I want disaster recovery procedures with tested failover, so that the business can continue operating during catastrophic failures.

#### Acceptance Criteria

**Disaster Recovery Planning:**

1. THE System SHALL document disaster recovery plan in docs/DISASTER_RECOVERY.md
2. THE System SHALL define Recovery Time Objective (RTO): 4 hours for full service restoration
3. THE System SHALL define Recovery Point Objective (RPO): 15 minutes of data loss maximum
4. THE System SHALL identify critical dependencies: database, KoraPay API, email service
5. THE System SHALL identify single points of failure and mitigation strategies
6. THE System SHALL document failover procedures for each critical component
7. THE System SHALL document data restoration procedures from backups
8. THE System SHALL document communication plan during disaster
9. THE System SHALL document escalation procedures for disaster scenarios
10. THE System SHALL conduct disaster recovery drill annually

**Backup Strategy:**

11. THE System SHALL create full database backup daily at 2 AM UTC
12. THE System SHALL create incremental database backup every 15 minutes
13. THE System SHALL retain daily backups for 30 days
14. THE System SHALL retain weekly backups for 1 year
15. THE System SHALL retain monthly backups for 7 years (compliance)
16. THE System SHALL encrypt all backups using AES-256
17. THE System SHALL store backups in geographically separate location
18. THE System SHALL verify backup integrity daily by test restore
19. THE System SHALL monitor backup success and alert on failure
20. THE System SHALL document backup procedures in docs/BACKUP_PROCEDURES.md

**Failover Procedures:**

21. THE System SHALL support automatic database failover to standby replica within 60 seconds
22. THE System SHALL support manual database failover with documented procedure
23. THE System SHALL support application failover to secondary region within 15 minutes
24. THE System SHALL maintain transaction consistency during failover (no data loss)
25. THE System SHALL verify data integrity after failover using checksums
26. THE System SHALL test failover procedures quarterly in staging environment
27. THE System SHALL document failover procedures in docs/FAILOVER.md
28. THE System SHALL implement failover monitoring and alerting
29. THE System SHALL log all failover events to audit log
30. THE System SHALL conduct post-failover review and document lessons learned

**Data Restoration:**

31. THE System SHALL support point-in-time recovery (PITR) to any point in last 30 days
32. THE System SHALL support selective data restoration (single transaction or user)
33. THE System SHALL support full database restoration from backup within 2 hours
34. THE System SHALL verify restored data integrity using checksums
35. THE System SHALL test data restoration procedures quarterly
36. THE System SHALL document data restoration procedures in docs/DATA_RESTORATION.md
37. THE System SHALL implement restoration monitoring and progress tracking
38. THE System SHALL log all restoration events to audit log
39. THE System SHALL require dual approval for production data restoration
40. THE System SHALL conduct post-restoration verification and testing

**Business Continuity:**

41. THE System SHALL maintain read-only mode during KoraPay API outage (view transactions)
42. THE System SHALL queue payment link creation requests during outage for processing when restored
43. THE System SHALL notify merchants of service degradation via dashboard banner
44. THE System SHALL provide status page showing current system health and incidents
45. THE System SHALL document business continuity plan in docs/BUSINESS_CONTINUITY.md
46. THE System SHALL identify critical business functions and maximum tolerable downtime
47. THE System SHALL implement workarounds for extended outages (manual payment processing)
48. THE System SHALL maintain communication channels during outage (status page, email, SMS)
49. THE System SHALL conduct business continuity exercise annually
50. THE System SHALL review and update business continuity plan quarterly

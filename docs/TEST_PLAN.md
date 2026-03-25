# OnePay Comprehensive Test Plan

**Date:** March 24, 2026  
**Purpose:** Verify all features work correctly after security fixes

---

## Test Categories

1. Authentication & Authorization
2. Payment Link Creation
3. Payment Verification Flow
4. Transaction Management
5. Webhook Delivery
6. Rate Limiting
7. Security Controls
8. Frontend Functionality
9. Backend API Endpoints
10. Database Operations

---

## 1. Authentication & Authorization Tests

### 1.1 User Registration
- [ ] Register with valid credentials
- [ ] Register with duplicate username (should fail)
- [ ] Register with duplicate email (should fail)
- [ ] Register with weak password (should fail)
- [ ] Register with invalid email format (should fail)
- [ ] Register with username too short (should fail)
- [ ] Register with common password (should fail)
- [ ] Verify session is created after registration
- [ ] Verify CSRF token is generated
- [ ] Verify password is hashed with bcrypt (13 rounds)

### 1.2 User Login
- [ ] Login with valid credentials
- [ ] Login with wrong password (should fail)
- [ ] Login with non-existent user (should fail)
- [ ] Login without CSRF token (should fail)
- [ ] Verify session regeneration after login
- [ ] Verify failed login attempts are tracked
- [ ] Verify account lockout after 5 failed attempts
- [ ] Verify lockout expires after 15 minutes

### 1.3 Password Reset
- [ ] Request password reset for existing user
- [ ] Request password reset for non-existent user (no info leak)
- [ ] Reset password with valid token
- [ ] Reset password with expired token (should fail)
- [ ] Reset password with invalid token (should fail)
- [ ] Verify new password cannot be same as old
- [ ] Verify reset token is invalidated after use

### 1.4 Session Management
- [ ] Verify session expires after 30 minutes inactivity
- [ ] Verify session expires after 7 days absolute
- [ ] Verify logout clears session
- [ ] Verify session survives app restart (boot time check)
- [ ] Verify unauthenticated access redirects to login

---

## 2. Payment Link Creation Tests

### 2.1 Basic Link Creation
- [ ] Create link with minimum required fields (amount only)
- [ ] Create link with all optional fields
- [ ] Create link with description
- [ ] Create link with customer email
- [ ] Create link with customer phone
- [ ] Create link with return URL
- [ ] Create link with webhook URL
- [ ] Verify transaction reference is generated (ONEPAY-XXX)
- [ ] Verify hash token is generated
- [ ] Verify expiration time is set correctly

### 2.2 Amount Validation
- [ ] Create link with valid decimal amount
- [ ] Create link with zero amount (should fail)
- [ ] Create link with negative amount (should fail)
- [ ] Create link with amount > 100M (should fail)
- [ ] Create link with invalid amount format (should fail)
- [ ] Create link with NaN (should fail)
- [ ] Create link with Infinity (should fail)
- [ ] Verify amount is stored with 2 decimal places

### 2.3 Idempotency
- [ ] Create link with idempotency key
- [ ] Create duplicate link with same key (should return existing)
- [ ] Create link with different key (should create new)
- [ ] Verify idempotency key validation (alphanumeric only)

### 2.4 Virtual Account Creation
- [ ] Verify virtual account is created in mock mode
- [ ] Verify account number is generated
- [ ] Verify bank name is set
- [ ] Verify account name is set

### 2.5 Rate Limiting
- [ ] Create 10 links rapidly (should succeed)
- [ ] Create 11th link (should be rate limited)
- [ ] Wait 60 seconds and retry (should succeed)

---

## 3. Payment Verification Flow Tests

### 3.1 Payment Page Access
- [ ] Access payment page with valid tx_ref
- [ ] Access payment page with invalid tx_ref (should show error)
- [ ] Access payment page with expired link (should show error)
- [ ] Access payment page with tampered hash (should show error)
- [ ] Verify rate limiting on payment page (5 attempts per 5 min)

### 3.2 Payment Preview API
- [ ] Get preview with valid tx_ref
- [ ] Get preview without session access (should fail)
- [ ] Verify hash token is NOT exposed in response
- [ ] Verify all payment details are returned

### 3.3 Transfer Status Polling
- [ ] Poll status for pending transaction
- [ ] Poll status multiple times (mock mode: pending → confirmed)
- [ ] Poll status for expired transaction
- [ ] Poll status for already confirmed transaction
- [ ] Verify rate limiting (20 polls per minute)
- [ ] Verify no race conditions with concurrent polls

### 3.4 Payment Confirmation
- [ ] Verify transaction status changes to VERIFIED
- [ ] Verify verified_at timestamp is set
- [ ] Verify transfer_confirmed flag is set
- [ ] Verify is_used flag is set
- [ ] Verify audit log entry is created
- [ ] Verify webhook is delivered (if configured)

---

## 4. Transaction Management Tests

### 4.1 Transaction Status
- [ ] Get status for own transaction
- [ ] Get status for other user's transaction (should fail)
- [ ] Get status with invalid tx_ref format (should fail)
- [ ] Verify constant-time ownership check (no timing leak)

### 4.2 Transaction History
- [ ] Get transaction history (paginated)
- [ ] Get history page 2
- [ ] Verify pagination metadata
- [ ] Verify only own transactions are returned
- [ ] Verify transactions are ordered by created_at DESC

### 4.3 Transaction Export
- [ ] Export transactions as CSV
- [ ] Verify CSV contains all fields
- [ ] Verify rate limiting (5 exports per 5 minutes)

### 4.4 Transaction Re-issue
- [ ] Re-issue expired link
- [ ] Re-issue with same amount and details
- [ ] Verify new tx_ref is generated
- [ ] Verify new expiration time is set
- [ ] Cannot re-issue verified transaction (should fail)

### 4.5 Transaction Audit
- [ ] Get audit logs for transaction
- [ ] Verify all events are logged
- [ ] Verify rate limiting (20 requests per minute)

### 4.6 Receipt Generation
- [ ] Download receipt for verified transaction
- [ ] Verify HTML receipt is generated
- [ ] Verify rate limiting (10 requests per minute)

---

## 5. Webhook Delivery Tests

### 5.1 Webhook Configuration
- [ ] Set webhook URL (valid HTTPS)
- [ ] Set webhook URL (HTTP - should fail)
- [ ] Set webhook URL (localhost - should fail)
- [ ] Set webhook URL (private IP - should fail)
- [ ] Clear webhook URL
- [ ] Verify audit log for webhook changes

### 5.2 Webhook Delivery
- [ ] Verify webhook is sent on payment confirmation
- [ ] Verify HMAC signature is included
- [ ] Verify payload contains all required fields
- [ ] Verify User-Agent header is set
- [ ] Verify Content-Type is application/json

### 5.3 Webhook Retries
- [ ] Verify retry on failure (3 attempts)
- [ ] Verify exponential backoff with jitter
- [ ] Verify DNS validation on each retry
- [ ] Verify webhook_attempts counter increments
- [ ] Verify webhook_delivered flag is set on success
- [ ] Verify webhook_last_error is set on failure

### 5.4 Webhook Security
- [ ] Verify DNS rebinding protection
- [ ] Verify redirect prevention
- [ ] Verify response size limit (1MB)
- [ ] Verify timeout (10 seconds)

---

## 6. Rate Limiting Tests

### 6.1 Authentication Endpoints
- [ ] Login: 5 attempts per 60 seconds per IP
- [ ] Register: 3 attempts per hour per IP
- [ ] Password reset: 3 attempts per 5 minutes per IP
- [ ] Password reset: 2 attempts per hour per user

### 6.2 Payment Endpoints
- [ ] Create link: 10 per minute per user
- [ ] Verify page: 5 per 5 minutes per IP
- [ ] Transfer status: 20 per minute per IP
- [ ] Export: 5 per 5 minutes per user
- [ ] Summary: 20 per minute per user
- [ ] Receipt: 10 per minute per user
- [ ] Audit: 20 per minute per user

### 6.3 Rate Limit Behavior
- [ ] Verify 429 status code on limit exceeded
- [ ] Verify rate limit resets after window
- [ ] Verify rate limits persist across app restarts
- [ ] Verify rate limits work across multiple workers

---

## 7. Security Controls Tests

### 7.1 CSRF Protection
- [ ] POST without CSRF token (should fail)
- [ ] POST with invalid CSRF token (should fail)
- [ ] POST with valid CSRF token (should succeed)
- [ ] POST with wrong Content-Type (should fail)
- [ ] POST with wrong Origin header (should fail)

### 7.2 Session Security
- [ ] Verify HttpOnly flag is set
- [ ] Verify Secure flag is set (HTTPS mode)
- [ ] Verify SameSite=Lax is set
- [ ] Verify session regeneration on login
- [ ] Verify session fixation is prevented

### 7.3 Input Validation
- [ ] SQL injection attempts (should be blocked)
- [ ] XSS attempts (should be escaped)
- [ ] Path traversal attempts (should be blocked)
- [ ] Null byte injection (should be filtered)
- [ ] Control character injection (should be filtered)

### 7.4 Security Headers
- [ ] Verify Content-Security-Policy
- [ ] Verify X-Frame-Options: DENY
- [ ] Verify X-Content-Type-Options: nosniff
- [ ] Verify Referrer-Policy
- [ ] Verify Permissions-Policy
- [ ] Verify HSTS (HTTPS mode)

---

## 8. Frontend Functionality Tests

### 8.1 Dashboard
- [ ] Dashboard loads for authenticated user
- [ ] Dashboard redirects unauthenticated user
- [ ] Create payment form is displayed
- [ ] Webhook URL field is pre-filled

### 8.2 Payment Link Creation Form
- [ ] Amount field validation
- [ ] Description field (optional)
- [ ] Customer email validation
- [ ] Customer phone validation
- [ ] Return URL validation
- [ ] Webhook URL validation
- [ ] Form submission creates link
- [ ] Payment URL is displayed
- [ ] Virtual account details are shown

### 8.3 Payment Verification Page
- [ ] Page loads with transaction details
- [ ] Virtual account details are displayed
- [ ] Countdown timer shows expiration
- [ ] Polling starts automatically
- [ ] Status updates on confirmation
- [ ] Return URL button appears on success
- [ ] Error message on expiration

### 8.4 Transaction History Page
- [ ] History table loads
- [ ] Pagination controls work
- [ ] Status badges display correctly
- [ ] Re-issue button for expired links
- [ ] View receipt button for verified transactions

### 8.5 Settings Page
- [ ] Webhook URL field
- [ ] Save button works
- [ ] Success message on save
- [ ] Error message on invalid URL

---

## 9. Backend API Endpoints Tests

### 9.1 Public Endpoints
- [ ] GET /health (no auth required)
- [ ] GET /pay/<tx_ref> (no auth required)
- [ ] GET /api/payments/preview/<tx_ref> (session required)
- [ ] GET /api/payments/transfer-status/<tx_ref> (session required)

### 9.2 Authenticated Endpoints
- [ ] POST /api/payments/link (auth required)
- [ ] GET /api/payments/status/<tx_ref> (auth required)
- [ ] GET /api/payments/history (auth required)
- [ ] GET /api/payments/export (auth required)
- [ ] GET /api/payments/summary (auth required)
- [ ] POST /api/payments/reissue/<tx_ref> (auth required)
- [ ] GET /api/payments/audit/<tx_ref> (auth required)
- [ ] GET /api/payments/receipt/<tx_ref> (auth required)
- [ ] POST /api/account/settings (auth required)
- [ ] POST /api/settings/webhook (auth required)

### 9.3 Error Handling
- [ ] 404 for non-existent routes
- [ ] 401 for unauthenticated access
- [ ] 403 for CSRF failures
- [ ] 400 for validation errors
- [ ] 429 for rate limit exceeded
- [ ] 500 for internal errors (no stack trace leak)

---

## 10. Database Operations Tests

### 10.1 User Model
- [ ] Create user with hashed password
- [ ] Check password (correct)
- [ ] Check password (incorrect)
- [ ] Record failed login
- [ ] Record successful login
- [ ] Check account lockout
- [ ] Set reset token
- [ ] Verify reset token expiration

### 10.2 Transaction Model
- [ ] Create transaction
- [ ] Check expiration
- [ ] Update status
- [ ] Set verified_at timestamp
- [ ] to_dict() excludes hash_token
- [ ] effective_status_value() handles expiration

### 10.3 Audit Log Model
- [ ] Create audit log entry
- [ ] Query by event type
- [ ] Query by user_id
- [ ] Query by tx_ref
- [ ] Cleanup old logs (90 days)

### 10.4 Rate Limit Model
- [ ] Create rate limit entry
- [ ] Increment counter
- [ ] Check window expiration
- [ ] Cleanup old entries (2 hours)

---

## Test Execution

### Manual Testing
```bash
# 1. Start application
python app.py

# 2. Open browser
http://localhost:5000

# 3. Test each feature manually
```

### Automated Testing
```bash
# Run test suite
APP_ENV=testing python -m pytest tests/test_app.py -v

# Run with coverage
APP_ENV=testing python -m pytest tests/test_app.py --cov=. --cov-report=html
```

### Load Testing
```bash
# Test concurrent payment confirmations
ab -n 100 -c 10 http://localhost:5000/api/payments/transfer-status/ONEPAY-XXX

# Test rate limiting
ab -n 50 -c 5 http://localhost:5000/api/payments/summary
```

---

## Success Criteria

- [ ] All authentication flows work correctly
- [ ] Payment links can be created and verified
- [ ] Transactions are tracked accurately
- [ ] Webhooks are delivered reliably
- [ ] Rate limits prevent abuse
- [ ] Security controls block attacks
- [ ] Frontend is responsive and functional
- [ ] API endpoints return correct responses
- [ ] Database operations are consistent
- [ ] No errors in application logs

---

## Test Results

**Date:** _____________  
**Tester:** _____________  
**Environment:** _____________

**Overall Status:** ⬜ PASS / ⬜ FAIL

**Notes:**
_____________________________________________
_____________________________________________
_____________________________________________

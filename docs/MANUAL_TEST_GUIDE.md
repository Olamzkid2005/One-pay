# OnePay Manual Testing Guide

**Purpose:** Step-by-step manual testing procedures for all features  
**Date:** March 24, 2026

---

## Prerequisites

1. Application is running: `python app.py`
2. Browser is open: `http://localhost:5000`
3. Database is initialized: `alembic upgrade head`
4. Environment variables are set in `.env`

---

## Test 1: User Registration & Authentication

### 1.1 Register New User
**Steps:**
1. Navigate to `http://localhost:5000/register`
2. Enter username: `testuser1`
3. Enter email: `testuser1@example.com`
4. Enter password: `SecurePass123!`
5. Confirm password: `SecurePass123!`
6. Click "Register"

**Expected Result:**
- ✅ Redirected to dashboard
- ✅ Welcome message displayed
- ✅ Session created (check browser cookies)

**Security Verification:**
- ✅ Session ID changes after registration (session fixation fix)
- ✅ Password is hashed with bcrypt (13 rounds)

### 1.2 Login with Valid Credentials
**Steps:**
1. Logout if logged in
2. Navigate to `http://localhost:5000/login`
3. Enter username: `testuser1`
4. Enter password: `SecurePass123!`
5. Click "Login"

**Expected Result:**
- ✅ Redirected to dashboard
- ✅ Session created

**Security Verification:**
- ✅ Session ID changes after login (session fixation fix)

### 1.3 Test Account Lockout
**Steps:**
1. Logout
2. Try to login with wrong password 5 times
3. Try to login with correct password

**Expected Result:**
- ✅ After 5 failed attempts: "Account temporarily locked"
- ✅ Correct password also fails during lockout
- ✅ Wait 15 minutes or check database to unlock

### 1.4 Password Reset Flow
**Steps:**
1. Navigate to `http://localhost:5000/forgot-password`
2. Enter username: `testuser1`
3. Click "Reset Password"
4. Check console logs for reset link (no email configured)
5. Copy reset token from logs
6. Navigate to reset URL
7. Enter new password: `NewSecurePass456!`
8. Confirm password
9. Click "Reset Password"

**Expected Result:**
- ✅ Password updated successfully
- ✅ Can login with new password
- ✅ Cannot reuse reset token

---

## Test 2: Payment Link Creation

### 2.1 Create Basic Payment Link
**Steps:**
1. Login as `testuser1`
2. Navigate to dashboard
3. Enter amount: `1000`
4. Click "Create Payment Link"

**Expected Result:**
- ✅ Payment link created
- ✅ Transaction reference displayed (ONEPAY-XXX with 40 hex chars)
- ✅ Payment URL displayed
- ✅ Virtual account details shown (mock mode)
- ✅ Expiration time displayed

**Security Verification:**
- ✅ Transaction reference has 160 bits entropy (40 hex chars)
- ✅ Hash token is NOT exposed in UI

### 2.2 Create Link with All Fields
**Steps:**
1. Enter amount: `2500.50`
2. Enter description: `Invoice #12345`
3. Enter customer email: `customer@example.com`
4. Enter customer phone: `+2348012345678`
5. Enter return URL: `https://example.com/thanks`
6. Enter webhook URL: `https://example.com/webhook`
7. Click "Create Payment Link"

**Expected Result:**
- ✅ Link created with all details
- ✅ All fields saved correctly

### 2.3 Test Amount Validation
**Steps:**
1. Try amount: `0` → Should fail
2. Try amount: `-100` → Should fail
3. Try amount: `abc` → Should fail
4. Try amount: `1000.999` → Should round to 1000.00
5. Try amount: `100000001` → Should fail (exceeds max)

**Expected Result:**
- ✅ Invalid amounts rejected with error messages
- ✅ Valid amounts accepted

### 2.4 Test Rate Limiting
**Steps:**
1. Create 10 payment links rapidly
2. Try to create 11th link

**Expected Result:**
- ✅ First 10 succeed
- ✅ 11th returns "Too many requests"
- ✅ Wait 60 seconds and retry succeeds

---

## Test 3: Payment Verification Flow

### 3.1 Access Payment Page
**Steps:**
1. Copy payment URL from created link
2. Open in new browser tab (or incognito)
3. Observe payment page

**Expected Result:**
- ✅ Payment details displayed
- ✅ Amount shown correctly
- ✅ Virtual account details displayed
- ✅ Countdown timer shows expiration
- ✅ "Waiting for payment" status

### 3.2 Test Payment Confirmation (Mock Mode)
**Steps:**
1. Wait on payment page
2. Observe status polling (every 3 seconds)
3. After 3-4 polls, payment should confirm

**Expected Result:**
- ✅ Status changes to "Payment Confirmed"
- ✅ Success message displayed
- ✅ Return URL button appears (if configured)
- ✅ Transaction marked as verified in dashboard

**Security Verification:**
- ✅ No race conditions (check audit logs for single confirmation)
- ✅ Webhook delivered (if configured)

### 3.3 Test Expired Link
**Steps:**
1. Create payment link
2. Wait for expiration (or manually expire in database)
3. Try to access payment page

**Expected Result:**
- ✅ "Payment link has expired" message
- ✅ Cannot proceed with payment

---

## Test 4: Transaction Management

### 4.1 View Transaction History
**Steps:**
1. Login to dashboard
2. Navigate to "History" page
3. Observe transaction list

**Expected Result:**
- ✅ All transactions displayed
- ✅ Status badges show correct status
- ✅ Pagination works (if >20 transactions)
- ✅ Most recent transactions first

### 4.2 Check Transaction Status
**Steps:**
1. Navigate to "Check Status" page
2. Enter transaction reference
3. Click "Check Status"

**Expected Result:**
- ✅ Transaction details displayed
- ✅ Current status shown
- ✅ Amount and description correct

### 4.3 Re-issue Expired Link
**Steps:**
1. Find expired transaction in history
2. Click "Re-issue" button
3. Observe new payment link

**Expected Result:**
- ✅ New transaction created
- ✅ Same amount and details
- ✅ New transaction reference
- ✅ New expiration time

### 4.4 Export Transactions
**Steps:**
1. Navigate to history page
2. Click "Export CSV" button
3. Download CSV file

**Expected Result:**
- ✅ CSV file downloaded
- ✅ Contains all transactions
- ✅ All fields included

**Security Verification:**
- ✅ Rate limited (try 6 times, 6th should fail)

### 4.5 View Analytics Summary
**Steps:**
1. Navigate to dashboard
2. Observe summary statistics

**Expected Result:**
- ✅ Total collected amount shown
- ✅ Total links created
- ✅ Conversion rate calculated
- ✅ This month vs all-time stats

**Security Verification:**
- ✅ Rate limited (try 21 times, 21st should fail)

### 4.6 Download Receipt
**Steps:**
1. Find verified transaction
2. Click "Download Receipt"
3. Observe receipt

**Expected Result:**
- ✅ HTML receipt displayed
- ✅ All transaction details included
- ✅ Professional formatting

**Security Verification:**
- ✅ Rate limited (try 11 times, 11th should fail)

---

## Test 5: Webhook Configuration

### 5.1 Set Webhook URL
**Steps:**
1. Navigate to "Settings" page
2. Enter webhook URL: `https://example.com/webhook`
3. Click "Save"

**Expected Result:**
- ✅ Success message displayed
- ✅ Webhook URL saved

**Security Verification:**
- ✅ Audit log entry created for webhook change

### 5.2 Test Invalid Webhook URLs
**Steps:**
1. Try HTTP URL: `http://example.com/webhook` → Should fail
2. Try localhost: `https://localhost/webhook` → Should fail
3. Try private IP: `https://192.168.1.1/webhook` → Should fail
4. Try with credentials: `https://user:pass@example.com/webhook` → Should fail

**Expected Result:**
- ✅ All invalid URLs rejected with error messages

### 5.3 Clear Webhook URL
**Steps:**
1. Clear webhook URL field
2. Click "Save"

**Expected Result:**
- ✅ Webhook URL removed
- ✅ Success message displayed

---

## Test 6: Security Controls

### 6.1 Test CSRF Protection
**Steps:**
1. Open browser developer tools
2. Try to submit form without CSRF token
3. Try to submit with invalid CSRF token

**Expected Result:**
- ✅ Requests rejected with "CSRF validation failed"

### 6.2 Test Session Expiration
**Steps:**
1. Login
2. Wait 30 minutes without activity
3. Try to access protected page

**Expected Result:**
- ✅ Redirected to login page
- ✅ "Session expired" message

### 6.3 Test Absolute Session Lifetime
**Steps:**
1. Login
2. Keep session active for 7+ days (or manually set in database)
3. Try to access protected page

**Expected Result:**
- ✅ Session expired even if recently active
- ✅ Redirected to login

### 6.4 Test XSS Protection
**Steps:**
1. Create payment link with description: `<script>alert('XSS')</script>`
2. View transaction in history
3. View payment page

**Expected Result:**
- ✅ Script tags are escaped (displayed as text)
- ✅ No JavaScript execution

### 6.5 Test SQL Injection Protection
**Steps:**
1. Try to check status with: `'; DROP TABLE users; --`
2. Try to login with username: `admin' OR '1'='1`

**Expected Result:**
- ✅ Invalid format errors
- ✅ No SQL injection possible

---

## Test 7: Rate Limiting Verification

### 7.1 Login Rate Limit
**Steps:**
1. Try to login 6 times rapidly (wrong password)

**Expected Result:**
- ✅ First 5 attempts processed
- ✅ 6th attempt: "Too many login attempts"

### 7.2 Registration Rate Limit
**Steps:**
1. Try to register 4 times from same IP

**Expected Result:**
- ✅ First 3 succeed (with different usernames)
- ✅ 4th attempt: "Too many registration attempts"

### 7.3 Payment Link Creation Rate Limit
**Steps:**
1. Create 11 payment links rapidly

**Expected Result:**
- ✅ First 10 succeed
- ✅ 11th: "Too many requests"

### 7.4 Export Rate Limit
**Steps:**
1. Export CSV 6 times rapidly

**Expected Result:**
- ✅ First 5 succeed
- ✅ 6th: "Too many requests"

---

## Test 8: Error Handling

### 8.1 Test 404 Errors
**Steps:**
1. Navigate to non-existent page: `http://localhost:5000/nonexistent`

**Expected Result:**
- ✅ 404 page displayed
- ✅ No stack trace exposed

### 8.2 Test 401 Errors
**Steps:**
1. Logout
2. Try to access: `http://localhost:5000/api/payments/history`

**Expected Result:**
- ✅ 401 Unauthorized
- ✅ Error message: "Authentication required"

### 8.3 Test 403 Errors
**Steps:**
1. Try to access another user's transaction

**Expected Result:**
- ✅ 403 Forbidden or 404 Not Found
- ✅ No information leakage

### 8.4 Test 500 Errors
**Steps:**
1. Cause internal error (e.g., invalid database query)

**Expected Result:**
- ✅ Generic error message
- ✅ No stack trace in response (only in logs)

---

## Test 9: Browser Compatibility

### 9.1 Test in Chrome
- [ ] All features work
- [ ] UI renders correctly
- [ ] No console errors

### 9.2 Test in Firefox
- [ ] All features work
- [ ] UI renders correctly
- [ ] No console errors

### 9.3 Test in Safari
- [ ] All features work
- [ ] UI renders correctly
- [ ] No console errors

### 9.4 Test in Edge
- [ ] All features work
- [ ] UI renders correctly
- [ ] No console errors

---

## Test 10: Mobile Responsiveness

### 10.1 Test on Mobile Device
**Steps:**
1. Open on mobile browser or use browser dev tools
2. Test all pages

**Expected Result:**
- ✅ Responsive layout
- ✅ All buttons accessible
- ✅ Forms usable
- ✅ No horizontal scrolling

---

## Security Verification Checklist

After completing all tests, verify:

- [ ] Session fixation is prevented (session ID changes on login/register)
- [ ] No race conditions in payment confirmation
- [ ] Passwords hashed with bcrypt 13 rounds
- [ ] CSRF protection works with Origin validation
- [ ] DNS rebinding protection on webhooks
- [ ] Timing attacks prevented (constant-time checks)
- [ ] Rate limiting works on all critical endpoints
- [ ] Session cookies configured correctly (SameSite=Lax)
- [ ] Absolute session lifetime enforced (7 days)
- [ ] No ReDoS vulnerabilities
- [ ] Input sanitization removes control characters
- [ ] Webhook retries use jitter
- [ ] Security headers present
- [ ] Transaction references have 160-bit entropy
- [ ] Audit logging for settings changes

---

## Test Results Template

**Date:** _____________  
**Tester:** _____________  
**Environment:** _____________  
**Browser:** _____________

| Test Category | Status | Notes |
|---------------|--------|-------|
| Authentication | ⬜ PASS / ⬜ FAIL | |
| Payment Links | ⬜ PASS / ⬜ FAIL | |
| Payment Flow | ⬜ PASS / ⬜ FAIL | |
| Transactions | ⬜ PASS / ⬜ FAIL | |
| Webhooks | ⬜ PASS / ⬜ FAIL | |
| Security | ⬜ PASS / ⬜ FAIL | |
| Rate Limiting | ⬜ PASS / ⬜ FAIL | |
| Error Handling | ⬜ PASS / ⬜ FAIL | |
| Browser Compat | ⬜ PASS / ⬜ FAIL | |
| Mobile | ⬜ PASS / ⬜ FAIL | |

**Overall Status:** ⬜ PASS / ⬜ FAIL

**Issues Found:**
_____________________________________________
_____________________________________________
_____________________________________________

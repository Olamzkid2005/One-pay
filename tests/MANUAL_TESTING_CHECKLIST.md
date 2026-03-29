# Google OAuth Integration - Manual Testing Checklist

This checklist covers manual testing scenarios for the Google OAuth integration feature.

## Prerequisites

- [ ] Google OAuth credentials configured in `.env` file
- [ ] Database migration applied (`alembic upgrade head`)
- [ ] Application running locally or deployed
- [ ] Test Google account with verified email

## Property 15: Traditional Registration Preservation

**Verify that traditional registration remains fully functional**

- [ ] Navigate to `/register` page
- [ ] Verify traditional registration form is displayed
- [ ] Fill in username, email, password, and confirm password
- [ ] Submit the form
- [ ] Verify account is created successfully
- [ ] Verify redirect to dashboard
- [ ] Logout and verify can login with username/password
- [ ] Verify traditional registration works exactly as before (no regressions)

## Property 16: Graceful Degradation

**Verify system works when Google OAuth is not configured**

### Test 1: OAuth Not Configured

- [ ] Stop the application
- [ ] Remove or comment out `GOOGLE_CLIENT_ID` from `.env`
- [ ] Start the application
- [ ] Navigate to `/register` page
- [ ] Verify Google Sign-In button is NOT displayed
- [ ] Verify no error messages are shown
- [ ] Verify traditional registration form is still functional
- [ ] Complete a traditional registration successfully

### Test 2: OAuth Configured

- [ ] Stop the application
- [ ] Add `GOOGLE_CLIENT_ID` back to `.env`
- [ ] Start the application
- [ ] Navigate to `/register` page
- [ ] Verify Google Sign-In button IS displayed
- [ ] Verify button appears below traditional form with separator

## Google Sign-In Button Display

**Verify Google Sign-In button appears correctly**

- [ ] Navigate to `/register` page
- [ ] Verify "Or continue with" separator is displayed
- [ ] Verify Google Sign-In button is displayed
- [ ] Verify button has Google branding (blue background, Google logo)
- [ ] Verify explanatory text: "Sign in with your Google account for quick registration"
- [ ] Verify button is visually distinct from traditional submit button
- [ ] Verify button is centered and properly styled

## Complete OAuth Flow - New Account

**Verify OAuth flow creates new account**

- [ ] Navigate to `/register` page
- [ ] Click "Sign in with Google" button
- [ ] Verify redirect to Google OAuth consent screen
- [ ] Sign in with a Google account that has NOT been used before
- [ ] Grant permissions (email, profile)
- [ ] Verify redirect back to application
- [ ] Verify redirect to dashboard (`/dashboard`)
- [ ] Verify welcome message: "Welcome, [username]! Your account has been created."
- [ ] Verify username was generated from email (e.g., `john_doe` from `john.doe@gmail.com`)
- [ ] Navigate to settings or profile page
- [ ] Verify profile picture is displayed (from Google)
- [ ] Verify full name is displayed (from Google)
- [ ] Verify email matches Google account email

## Complete OAuth Flow - Existing Account Linking

**Verify OAuth flow links to existing account**

### Setup: Create Traditional Account First

- [ ] Logout if logged in
- [ ] Navigate to `/register` page
- [ ] Create account using traditional registration with email: `test@example.com`
- [ ] Logout

### Test: Link Google Account

- [ ] Navigate to `/register` page
- [ ] Click "Sign in with Google" button
- [ ] Sign in with Google account using SAME email: `test@example.com`
- [ ] Verify redirect to dashboard
- [ ] Verify message: "Welcome back, [username]! Your Google account has been linked."
- [ ] Logout
- [ ] Verify can login with BOTH methods:
  - [ ] Login with username/password (traditional)
  - [ ] Login with Google Sign-In

## Session Persistence

**Verify session persists across page refreshes**

- [ ] Login via Google OAuth
- [ ] Verify redirect to dashboard
- [ ] Refresh the page (F5 or Ctrl+R)
- [ ] Verify still logged in (not redirected to login page)
- [ ] Navigate to different pages (settings, history, etc.)
- [ ] Verify session persists across all pages
- [ ] Close browser tab
- [ ] Open new tab and navigate to application
- [ ] Verify still logged in (session cookie persists)

## Logout

**Verify logout clears session**

- [ ] Login via Google OAuth
- [ ] Click logout button
- [ ] Verify redirect to login page
- [ ] Verify message: "You have been logged out."
- [ ] Try to access protected page (e.g., `/dashboard`)
- [ ] Verify redirect to login page (session cleared)
- [ ] Navigate to `/register` page
- [ ] Verify NOT automatically logged in

## Rate Limiting

**Verify rate limiting triggers after 5 attempts**

- [ ] Open browser developer tools (F12)
- [ ] Navigate to `/register` page
- [ ] Click "Sign in with Google" button
- [ ] Cancel the Google OAuth flow (close popup or click back)
- [ ] Repeat 4 more times (total 5 attempts)
- [ ] On the 6th attempt, verify error message: "Too many authentication attempts"
- [ ] Verify HTTP 429 status code in network tab
- [ ] Wait 60 seconds
- [ ] Try again, verify rate limit is reset

## CSRF Protection

**Verify CSRF validation prevents forged requests**

- [ ] Open browser developer tools (F12)
- [ ] Navigate to `/register` page
- [ ] Open Console tab
- [ ] Execute JavaScript to send request with invalid CSRF token:
```javascript
fetch('/auth/google/callback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    credential: 'fake.token',
    csrf_token: 'invalid-token'
  })
}).then(r => r.json()).then(console.log)
```
- [ ] Verify response has `success: false`
- [ ] Verify error message mentions CSRF or session expired
- [ ] Verify HTTP 403 status code

## Unverified Email

**Verify unverified email shows error message**

Note: This requires a Google account with unverified email, which is rare. Skip if not available.

- [ ] Navigate to `/register` page
- [ ] Click "Sign in with Google" button
- [ ] Sign in with Google account that has unverified email
- [ ] Verify error message: "Please verify your email address with Google before signing in."
- [ ] Verify HTTP 401 status code
- [ ] Verify NOT logged in

## Invalid Token

**Verify invalid token shows error message**

This is difficult to test manually. Verify through automated tests or by:

- [ ] Check server logs for token validation errors
- [ ] Verify error messages are user-friendly (no technical details)
- [ ] Verify HTTP 401 status code for invalid tokens

## Account Linking Conflict

**Verify account linking conflict is rejected**

### Setup: Create Two Accounts

- [ ] Create traditional account with email: `test1@example.com`
- [ ] Logout
- [ ] Login with Google using email: `test2@example.com`
- [ ] Logout

### Test: Attempt to Link Different Google Account

- [ ] Manually change email in database:
  - Update user with email `test1@example.com` to have `google_id` = '1111111111'
- [ ] Navigate to `/register` page
- [ ] Click "Sign in with Google" button
- [ ] Sign in with Google account: `test1@example.com` (which will have different google_id)
- [ ] Verify error message: "This email is already linked to a different Google account."
- [ ] Verify HTTP 409 status code
- [ ] Verify NOT logged in

## Audit Logging

**Verify audit logs capture all OAuth events**

- [ ] Login via Google OAuth (new account)
- [ ] Check database `audit_log` table
- [ ] Verify event: `oauth.account_created` with user_id and email
- [ ] Logout
- [ ] Login via Google OAuth (existing account)
- [ ] Check database `audit_log` table
- [ ] Verify event: `oauth.login` with user_id and email
- [ ] Attempt OAuth with invalid token (use developer tools to send bad request)
- [ ] Check database `audit_log` table
- [ ] Verify event: `oauth.authentication_failed` with IP address
- [ ] Verify NO tokens or secrets are logged in audit logs

## Security Verification

**Verify security controls are in place**

### No Token Storage

- [ ] Login via Google OAuth
- [ ] Check database `users` table for your account
- [ ] Verify `google_id` column is populated
- [ ] Verify NO columns for `access_token` or `refresh_token`
- [ ] Verify only Google user ID is stored

### Random Password for OAuth Accounts

- [ ] Create new account via Google OAuth
- [ ] Check database `users` table
- [ ] Verify `password_hash` column is populated (not null)
- [ ] Attempt to login with username/password using any password
- [ ] Verify login fails (OAuth accounts cannot use password login unless explicitly set)

### HTTPS in Production

- [ ] Check `.env` file
- [ ] Verify `GOOGLE_REDIRECT_URI` uses HTTPS in production
- [ ] Verify application enforces HTTPS in production (`ENFORCE_HTTPS=true`)

## Browser Compatibility

**Verify OAuth works across browsers**

- [ ] Test in Chrome/Chromium
  - [ ] Complete OAuth flow successfully
- [ ] Test in Firefox
  - [ ] Complete OAuth flow successfully
- [ ] Test in Safari (if available)
  - [ ] Complete OAuth flow successfully
- [ ] Test in Edge
  - [ ] Complete OAuth flow successfully

## Mobile Responsiveness

**Verify OAuth button displays correctly on mobile**

- [ ] Open browser developer tools
- [ ] Toggle device toolbar (mobile view)
- [ ] Navigate to `/register` page
- [ ] Verify Google Sign-In button is responsive
- [ ] Verify button is not cut off or misaligned
- [ ] Verify button is easily clickable on mobile
- [ ] Complete OAuth flow on mobile view

## Error Recovery

**Verify users can retry after errors**

- [ ] Navigate to `/register` page
- [ ] Click "Sign in with Google" button
- [ ] Cancel the OAuth flow
- [ ] Verify error message is displayed
- [ ] Verify can click "Sign in with Google" button again
- [ ] Complete OAuth flow successfully
- [ ] Verify account is created

## Summary

After completing all tests:

- [ ] All critical tests passed
- [ ] No regressions in traditional registration
- [ ] OAuth flow works for new accounts
- [ ] OAuth flow works for account linking
- [ ] Security controls verified
- [ ] Error handling works correctly
- [ ] Graceful degradation works when OAuth not configured

## Notes

Record any issues or observations here:

---

**Test Date:** _______________

**Tester:** _______________

**Environment:** [ ] Local Development [ ] Staging [ ] Production

**Result:** [ ] All Tests Passed [ ] Issues Found (see notes)

# Google OAuth Setup Guide

This guide explains how to configure Google OAuth 2.0 authentication for OnePay merchant registration.

## Overview

Google OAuth allows merchants to register and sign in using their Google accounts, providing a faster and more convenient authentication method alongside traditional username/password registration.

## Prerequisites

- A Google Cloud Platform account
- Access to the Google Cloud Console
- OnePay application deployed or running locally

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., "OnePay Authentication")
4. Click "Create"

## Step 2: Enable Google Identity Services

1. In your project, go to "APIs & Services" → "Library"
2. Search for "Google Identity Services"
3. Click "Enable"

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" user type (or "Internal" if using Google Workspace)
3. Click "Create"
4. Fill in required fields:
   - **App name**: OnePay
   - **User support email**: Your support email
   - **Developer contact email**: Your developer email
5. Click "Save and Continue"
6. On "Scopes" page, click "Add or Remove Scopes"
7. Add these scopes:
   - `openid`
   - `email`
   - `profile`
8. Click "Save and Continue"
9. Review and click "Back to Dashboard"

## Step 4: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Select "Web application" as application type
4. Enter name: "OnePay Web Client"
5. Add **Authorized JavaScript origins**:
   - For development: `http://localhost:5000`
   - For production: `https://yourdomain.com`
6. Add **Authorized redirect URIs**:
   - For development: `http://localhost:5000/auth/google/callback`
   - For production: `https://yourdomain.com/auth/google/callback`
7. Click "Create"
8. Copy the **Client ID** and **Client Secret** (you'll need these for configuration)

## Step 5: Configure OnePay Environment Variables

Add the following variables to your `.env` file:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
```

### Development Configuration

For local development:

```bash
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
```

### Production Configuration

For production deployment:

```bash
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
```

**Important**: The `GOOGLE_REDIRECT_URI` must match exactly one of the authorized redirect URIs configured in Google Cloud Console.

## Step 6: Run Database Migration

Apply the database migration to add OAuth fields to the users table:

```bash
# Using Alembic
alembic upgrade head

# Or using the migrate script
python migrate.py
```

This adds the following columns to the `users` table:
- `google_id` - Google user ID
- `profile_picture_url` - User's profile picture URL
- `full_name` - User's full name
- `auth_provider` - Authentication method (traditional, google, or both)

## Step 7: Install Dependencies

Install the required Python package:

```bash
pip install -r requirements.txt
```

This installs `google-auth>=2.0.0` which is required for token validation.

## Step 8: Restart Application

Restart your OnePay application to load the new configuration:

```bash
# Development
python app.py

# Production with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Step 9: Verify Integration

1. Navigate to the registration page: `http://localhost:5000/register` (or your production URL)
2. You should see a "Sign in with Google" button below the traditional registration form
3. Click the button to test the OAuth flow
4. Authenticate with your Google account
5. You should be redirected to the dashboard with a new account created

## Security Considerations

### Production Requirements

The configuration validation enforces these security requirements in production:

1. **GOOGLE_CLIENT_SECRET** must be at least 32 characters
2. **GOOGLE_REDIRECT_URI** must use HTTPS (not HTTP)
3. Never commit secrets to version control

### Token Security

- OAuth access tokens and refresh tokens are **never stored** in the database
- Only the Google user ID (`sub` claim) is persisted for future authentication
- ID tokens are validated once and discarded immediately

### Rate Limiting

Google OAuth endpoints are rate-limited to prevent abuse:
- 5 authentication attempts per IP address per 60 seconds
- Rate limit violations are logged for security monitoring

## Troubleshooting

### Google Sign-In Button Not Appearing

**Cause**: `GOOGLE_CLIENT_ID` is not configured or invalid

**Solution**:
1. Verify `GOOGLE_CLIENT_ID` is set in `.env`
2. Check that the client ID matches the one from Google Cloud Console
3. Restart the application

### "redirect_uri_mismatch" Error

**Cause**: The redirect URI doesn't match the authorized URIs in Google Cloud Console

**Solution**:
1. Go to Google Cloud Console → Credentials
2. Edit your OAuth 2.0 Client ID
3. Add the exact redirect URI to "Authorized redirect URIs"
4. Wait a few minutes for changes to propagate

### "Email address is not verified" Error

**Cause**: The Google account's email is not verified

**Solution**:
1. Log into the Google account
2. Go to Account Settings → Personal Info
3. Verify the email address
4. Try signing in again

### "Authentication failed" Error

**Cause**: Token validation failed (expired, invalid signature, wrong audience)

**Solution**:
1. Check server logs for detailed error message
2. Verify `GOOGLE_CLIENT_ID` matches the client ID in Google Cloud Console
3. Ensure system clock is synchronized (token expiration validation requires accurate time)

### Account Linking Conflict

**Cause**: Email is already linked to a different Google account

**Solution**:
- This is expected behavior to prevent account takeover
- User must use the original Google account or traditional login
- Contact support if legitimate account access issue

## Testing

### Manual Testing Checklist

- [ ] Google Sign-In button appears on registration page
- [ ] Clicking button redirects to Google OAuth
- [ ] Successful authentication creates account and redirects to dashboard
- [ ] Existing email links to Google account (if not already linked)
- [ ] Session persists across page refreshes
- [ ] Logout clears session
- [ ] Rate limiting triggers after 5 attempts
- [ ] Unverified email shows error message
- [ ] Invalid token shows error message
- [ ] Google OAuth disabled when not configured (button hidden)

### Test Accounts

For testing, create test Google accounts or use Google's test users feature:

1. Go to Google Cloud Console → OAuth consent screen
2. Add test users under "Test users"
3. These users can authenticate even if the app is not verified

## Support

For issues or questions:
- Check the [OnePay documentation](docs/README.md)
- Review server logs for detailed error messages
- Contact the development team

## References

- [Google Identity Services Documentation](https://developers.google.com/identity/gsi/web)
- [OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google Cloud Console](https://console.cloud.google.com/)

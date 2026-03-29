# Requirements Document: Google OAuth Integration

## Introduction

This document specifies requirements for integrating Google OAuth 2.0 authentication into the OnePay merchant registration system. The integration will provide merchants with an alternative authentication method using their Google accounts, while maintaining the existing traditional username/password registration flow. The system will securely handle OAuth tokens, extract user profile information, and manage authenticated sessions with the same security standards as the existing authentication system.

## Glossary

- **OAuth_Client**: The Google OAuth 2.0 client library component that handles authentication flow with Google's identity platform
- **Registration_Page**: The merchant account creation page that displays both traditional and Google Sign-In options
- **Session_Manager**: The Flask session management component that maintains user authentication state
- **Profile_Extractor**: The component that retrieves user information from Google's identity service
- **Token_Validator**: The component that verifies Google OAuth tokens server-side
- **User_Repository**: The database access layer for user account operations
- **Auth_Controller**: The Flask blueprint controller handling authentication routes
- **Google_Identity_Service**: Google's OAuth 2.0 identity platform API

## Requirements

### Requirement 1: Google Sign-In Button Display

**User Story:** As a merchant, I want to see a Google Sign-In button on the registration page, so that I can choose between traditional registration and Google authentication.

#### Acceptance Criteria

1. THE Registration_Page SHALL display a Google Sign-In button below the traditional registration form
2. THE Registration_Page SHALL visually distinguish the Google Sign-In button from the traditional submit button using Google's brand guidelines
3. THE Registration_Page SHALL display explanatory text indicating that Google Sign-In is an alternative authentication method
4. THE Registration_Page SHALL maintain the existing traditional registration form without modification
5. WHEN the Registration_Page loads, THE OAuth_Client SHALL initialize the Google Identity Services library

### Requirement 2: OAuth 2.0 Authentication Flow

**User Story:** As a merchant, I want to authenticate using my Google account, so that I can register without creating a new password.

#### Acceptance Criteria

1. WHEN a merchant clicks the Google Sign-In button, THE OAuth_Client SHALL initiate the OAuth 2.0 authorization flow
2. THE OAuth_Client SHALL request the following scopes: email, profile, openid
3. WHEN Google returns an authorization code, THE OAuth_Client SHALL send it to the backend for validation
4. THE Token_Validator SHALL verify the authorization code with Google's token endpoint
5. IF the authorization code is invalid, THEN THE Token_Validator SHALL return an error and THE Registration_Page SHALL display a user-friendly error message
6. WHEN the authorization code is valid, THE Token_Validator SHALL exchange it for an access token and ID token
7. THE Token_Validator SHALL verify the ID token signature using Google's public keys
8. THE Token_Validator SHALL validate the ID token audience matches the OAuth client ID
9. THE Token_Validator SHALL validate the ID token issuer is accounts.google.com
10. IF token validation fails, THEN THE Auth_Controller SHALL reject the authentication attempt and log the failure

### Requirement 3: User Profile Data Extraction

**User Story:** As a merchant, I want my Google profile information automatically populated, so that I don't have to manually enter my name and email.

#### Acceptance Criteria

1. WHEN the ID token is validated, THE Profile_Extractor SHALL extract the email address from the token claims
2. THE Profile_Extractor SHALL extract the full name from the token claims
3. THE Profile_Extractor SHALL extract the profile picture URL from the token claims
4. IF the email address is not verified in the Google account, THEN THE Auth_Controller SHALL reject the registration
5. THE Profile_Extractor SHALL normalize the email address to lowercase before storage

### Requirement 4: User Account Creation via Google OAuth

**User Story:** As a merchant, I want an account automatically created when I sign in with Google, so that I can immediately access the platform.

#### Acceptance Criteria

1. WHEN a merchant authenticates via Google for the first time, THE User_Repository SHALL check if an account with the Google email already exists
2. IF an account with the email exists and was created via traditional registration, THEN THE Auth_Controller SHALL link the Google authentication to the existing account
3. IF no account exists, THE User_Repository SHALL create a new user account with the Google email address
4. THE User_Repository SHALL generate a unique username from the Google email address (email prefix with numeric suffix if needed for uniqueness)
5. THE User_Repository SHALL store a flag indicating the account uses Google OAuth authentication
6. THE User_Repository SHALL store the Google user ID for future authentication attempts
7. THE User_Repository SHALL set a random secure password hash for Google-authenticated accounts to prevent password-based login
8. WHEN creating a Google-authenticated account, THE User_Repository SHALL store the profile picture URL
9. WHEN creating a Google-authenticated account, THE User_Repository SHALL store the full name

### Requirement 5: Session Management for Google-Authenticated Users

**User Story:** As a merchant, I want to remain logged in after Google authentication, so that I can access my dashboard without repeated logins.

#### Acceptance Criteria

1. WHEN Google authentication succeeds, THE Session_Manager SHALL create a new session using the secure session regeneration function
2. THE Session_Manager SHALL store the user ID in the session
3. THE Session_Manager SHALL store the username in the session
4. THE Session_Manager SHALL bind the session to the client IP address
5. THE Session_Manager SHALL bind the session to the client User-Agent
6. THE Session_Manager SHALL set the session as permanent with the configured lifetime
7. THE Session_Manager SHALL generate a new CSRF token for the session
8. WHEN a Google-authenticated user returns, THE Session_Manager SHALL validate the session using the same security checks as traditional authentication

### Requirement 6: Security Token Storage

**User Story:** As a system administrator, I want OAuth tokens securely stored, so that user credentials are protected from unauthorized access.

#### Acceptance Criteria

1. THE Auth_Controller SHALL NOT store Google access tokens in the database
2. THE Auth_Controller SHALL NOT store Google refresh tokens in the database
3. THE User_Repository SHALL store only the Google user ID for authentication verification
4. THE OAuth_Client SHALL retrieve the OAuth client ID from environment variables
5. THE OAuth_Client SHALL retrieve the OAuth client secret from environment variables
6. IF the OAuth client ID is not configured, THEN THE Registration_Page SHALL NOT display the Google Sign-In button
7. THE Token_Validator SHALL use HTTPS for all communication with Google's token endpoint

### Requirement 7: Rate Limiting for OAuth Attempts

**User Story:** As a system administrator, I want OAuth authentication attempts rate-limited, so that the system is protected from abuse.

#### Acceptance Criteria

1. THE Auth_Controller SHALL apply rate limiting to the Google OAuth callback endpoint
2. THE Auth_Controller SHALL limit Google OAuth attempts to 5 per IP address per 60 seconds
3. IF the rate limit is exceeded, THEN THE Auth_Controller SHALL return an HTTP 429 error
4. THE Auth_Controller SHALL log rate limit violations for security monitoring

### Requirement 8: Error Handling and User Feedback

**User Story:** As a merchant, I want clear error messages when Google authentication fails, so that I understand what went wrong and can take corrective action.

#### Acceptance Criteria

1. WHEN Google authentication is cancelled by the user, THE Registration_Page SHALL display a message indicating authentication was cancelled
2. WHEN Google authentication fails due to network issues, THE Registration_Page SHALL display a message suggesting the user retry
3. WHEN Google authentication fails due to invalid tokens, THE Registration_Page SHALL display a generic error message without exposing technical details
4. WHEN Google authentication fails due to unverified email, THE Registration_Page SHALL display a message requesting the user verify their Google account email
5. THE Auth_Controller SHALL log all authentication failures with sufficient detail for debugging without logging sensitive tokens
6. IF Google authentication fails, THEN THE Registration_Page SHALL allow the user to retry or use traditional registration

### Requirement 9: Audit Logging for OAuth Events

**User Story:** As a system administrator, I want OAuth authentication events logged, so that I can monitor security and troubleshoot issues.

#### Acceptance Criteria

1. WHEN a merchant initiates Google authentication, THE Auth_Controller SHALL log the event with the client IP address
2. WHEN Google authentication succeeds, THE Auth_Controller SHALL log the event with the user ID and email address
3. WHEN Google authentication fails, THE Auth_Controller SHALL log the event with the failure reason and client IP address
4. WHEN a new account is created via Google OAuth, THE Auth_Controller SHALL log the event with the user ID and email address
5. WHEN an existing account is linked to Google OAuth, THE Auth_Controller SHALL log the event with the user ID
6. THE Auth_Controller SHALL NOT log OAuth tokens or client secrets in audit logs

### Requirement 10: Database Schema for OAuth Data

**User Story:** As a developer, I want the database schema extended to support OAuth data, so that Google authentication information can be persisted.

#### Acceptance Criteria

1. THE User_Repository SHALL add a google_id column to the users table for storing Google user IDs
2. THE User_Repository SHALL add a profile_picture_url column to the users table for storing profile image URLs
3. THE User_Repository SHALL add a full_name column to the users table for storing user display names
4. THE User_Repository SHALL add an auth_provider column to the users table indicating authentication method (traditional or google)
5. THE User_Repository SHALL create a unique index on the google_id column
6. THE User_Repository SHALL allow the google_id column to be nullable for traditional accounts
7. THE User_Repository SHALL allow the password_hash column to remain required for all accounts

### Requirement 11: Existing User Account Linking

**User Story:** As a merchant with an existing account, I want to link my Google account, so that I can use Google Sign-In for future logins.

#### Acceptance Criteria

1. WHEN a merchant authenticates via Google with an email matching an existing traditional account, THE Auth_Controller SHALL verify the account is not already linked to a different Google account
2. IF the account is not linked, THE Auth_Controller SHALL link the Google user ID to the existing account
3. WHEN linking accounts, THE User_Repository SHALL update the auth_provider to indicate both authentication methods are available
4. WHEN a linked account authenticates via Google, THE Session_Manager SHALL create a session identical to traditional login
5. IF the account is already linked to a different Google account, THEN THE Auth_Controller SHALL reject the authentication and display an error message

### Requirement 12: Configuration and Environment Variables

**User Story:** As a system administrator, I want OAuth configuration managed via environment variables, so that credentials are not hardcoded.

#### Acceptance Criteria

1. THE OAuth_Client SHALL read GOOGLE_CLIENT_ID from environment variables
2. THE OAuth_Client SHALL read GOOGLE_CLIENT_SECRET from environment variables
3. THE OAuth_Client SHALL read GOOGLE_REDIRECT_URI from environment variables with a default value
4. IF GOOGLE_CLIENT_ID is not set, THEN THE Registration_Page SHALL NOT initialize the Google Sign-In button
5. THE Auth_Controller SHALL validate that GOOGLE_CLIENT_SECRET is at least 32 characters in production environments
6. THE Auth_Controller SHALL validate that GOOGLE_REDIRECT_URI uses HTTPS in production environments

### Requirement 13: Testing and Verification

**User Story:** As a developer, I want comprehensive tests for OAuth integration, so that the feature works reliably and securely.

#### Acceptance Criteria

1. THE test suite SHALL include unit tests for token validation logic
2. THE test suite SHALL include unit tests for profile extraction logic
3. THE test suite SHALL include integration tests for the complete OAuth flow
4. THE test suite SHALL include tests for error handling scenarios (invalid tokens, network failures, cancelled authentication)
5. THE test suite SHALL include tests for rate limiting on OAuth endpoints
6. THE test suite SHALL include tests for account creation via Google OAuth
7. THE test suite SHALL include tests for account linking scenarios
8. THE test suite SHALL include tests verifying OAuth tokens are not stored in the database
9. THE test suite SHALL include tests for session creation after Google authentication
10. THE test suite SHALL verify audit logging for all OAuth events

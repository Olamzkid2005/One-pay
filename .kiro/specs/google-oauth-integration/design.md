# Design Document: Google OAuth Integration

## Overview

This design implements Google OAuth 2.0 authentication as an alternative registration and login method for OnePay merchants. The integration follows the Authorization Code Flow with PKCE (Proof Key for Code Exchange) for enhanced security, leveraging Google Identity Services library for client-side OAuth initiation and implementing server-side token validation.

The design extends the existing authentication system without modifying traditional username/password flows. It adds database schema fields to support OAuth provider data, implements secure token validation on the backend, and provides seamless session management using the existing `_regenerate_session_secure` function. The implementation follows OnePay's established patterns for rate limiting, audit logging, CSRF protection, and error handling.

Key design decisions:
- **No token storage**: OAuth access/refresh tokens are never persisted to prevent credential exposure
- **Account linking**: Existing email-based accounts can be linked to Google authentication
- **Graceful degradation**: If Google OAuth is not configured, the feature is hidden without breaking traditional registration
- **Security-first**: All OAuth endpoints use rate limiting, CSRF protection, and comprehensive audit logging

## Architecture

### Component Overview

The Google OAuth integration consists of four primary layers:

**1. Frontend Layer (Client-Side OAuth Initiation)**
- Google Identity Services library loaded via CDN
- Sign-In button rendered on registration page
- OAuth flow initiated client-side with redirect to Google
- Authorization code received via callback URL

**2. Backend Layer (Token Validation & User Management)**
- Flask route `/auth/google/callback` handles OAuth callback
- Token validation service verifies ID tokens with Google's public keys
- Profile extraction service parses user data from token claims
- User repository handles account creation and linking logic

**3. Data Layer (Database Schema Extensions)**
- User model extended with OAuth-specific fields
- Alembic migration adds columns: `google_id`, `profile_picture_url`, `full_name`, `auth_provider`
- Unique index on `google_id` for fast lookups and constraint enforcement

**4. Security Layer (Rate Limiting & Audit Logging)**
- Rate limiting applied to OAuth callback endpoint
- Audit events logged for all OAuth authentication attempts
- CSRF protection on state parameter
- Session security using existing session regeneration

### Data Flow

```
┌─────────────┐
│   Merchant  │
│   Browser   │
└──────┬──────┘
       │ 1. Click "Sign in with Google"
       ▼
┌─────────────────────┐
│  Google Identity    │
│  Services (Client)  │
└──────┬──────────────┘
       │ 2. Redirect to Google OAuth
       ▼
┌─────────────────────┐
│  Google OAuth       │
│  Authorization      │
└──────┬──────────────┘
       │ 3. User authenticates & consents
       │ 4. Redirect to callback with code
       ▼
┌─────────────────────┐
│  /auth/google/      │
│  callback (Backend) │
└──────┬──────────────┘
       │ 5. Exchange code for tokens
       │ 6. Validate ID token
       ▼
┌─────────────────────┐
│  Token Validator    │
│  Service            │
└──────┬──────────────┘
       │ 7. Extract profile data
       ▼
┌─────────────────────┐
│  Profile Extractor  │
│  Service            │
└──────┬──────────────┘
       │ 8. Create/link account
       ▼
┌─────────────────────┐
│  User Repository    │
│  (Database)         │
└──────┬──────────────┘
       │ 9. Regenerate session
       ▼
┌─────────────────────┐
│  Session Manager    │
└──────┬──────────────┘
       │ 10. Redirect to dashboard
       ▼
┌─────────────────────┐
│  Merchant Dashboard │
└─────────────────────┘
```

### Technology Stack

- **Frontend**: Google Identity Services library (GSI), vanilla JavaScript
- **Backend**: Flask 3.x, Python 3.11+
- **OAuth Library**: `google-auth` (official Google authentication library)
- **Database**: SQLAlchemy ORM with Alembic migrations
- **Session Management**: Flask signed cookie sessions with server-side validation
- **Security**: Rate limiting via `services/rate_limiter.py`, audit logging via `core/audit.py`

## Components and Interfaces

### 1. Frontend: Google Sign-In Button

**File**: `templates/register.html` (modification)

**Responsibilities**:
- Load Google Identity Services library from CDN
- Render Google Sign-In button with proper styling
- Initialize OAuth client with client ID from backend
- Handle OAuth callback and error states

**Interface**:
```javascript
// Initialization
function initializeGoogleSignIn(clientId) {
  google.accounts.id.initialize({
    client_id: clientId,
    callback: handleGoogleCallback,
    auto_select: false
  });
  
  google.accounts.id.renderButton(
    document.getElementById("google-signin-button"),
    { theme: "filled_blue", size: "large", width: 400 }
  );
}

// Callback handler
function handleGoogleCallback(response) {
  // response.credential contains the ID token (JWT)
  // POST to /auth/google/callback with credential
}
```

**Dependencies**:
- Google Identity Services library: `https://accounts.google.com/gsi/client`
- Backend endpoint: `/auth/google/callback`
- CSRF token from session

### 2. Backend: OAuth Callback Route

**File**: `blueprints/auth.py` (new route)

**Route**: `POST /auth/google/callback`

**Responsibilities**:
- Receive ID token from frontend
- Validate CSRF token
- Apply rate limiting
- Delegate to token validator service
- Delegate to user management logic
- Create session and redirect

**Interface**:
```python
@auth_bp.route("/auth/google/callback", methods=["POST"])
def google_callback():
    """
    Handle Google OAuth callback.
    Receives ID token from frontend, validates it, and creates/links user account.
    """
    # 1. Validate CSRF token
    # 2. Check rate limit
    # 3. Extract ID token from request
    # 4. Validate token with TokenValidator
    # 5. Extract profile with ProfileExtractor
    # 6. Create/link account with UserRepository
    # 7. Regenerate session
    # 8. Log audit event
    # 9. Return success response
```

**Request Body**:
```json
{
  "credential": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "csrf_token": "..."
}
```

**Response**:
```json
{
  "success": true,
  "redirect_url": "/dashboard"
}
```

**Error Response**:
```json
{
  "success": false,
  "error": "Invalid token",
  "message": "Authentication failed. Please try again."
}
```

### 3. Service: Token Validator

**File**: `services/google_oauth.py` (new file)

**Class**: `GoogleTokenValidator`

**Responsibilities**:
- Verify ID token signature using Google's public keys
- Validate token claims (audience, issuer, expiration)
- Return validated token payload

**Interface**:
```python
class GoogleTokenValidator:
    def __init__(self, client_id: str):
        self.client_id = client_id
    
    def validate_token(self, id_token: str) -> dict:
        """
        Validate Google ID token and return payload.
        
        Args:
            id_token: JWT ID token from Google
        
        Returns:
            dict: Token payload with user claims
        
        Raises:
            ValueError: If token is invalid
        """
        # 1. Verify signature using Google's public keys
        # 2. Validate audience matches client_id
        # 3. Validate issuer is accounts.google.com
        # 4. Validate expiration
        # 5. Return payload
```

**Dependencies**:
- `google.auth.transport.requests`
- `google.oauth2.id_token`

### 4. Service: Profile Extractor

**File**: `services/google_oauth.py` (new file)

**Class**: `GoogleProfileExtractor`

**Responsibilities**:
- Extract user profile data from validated token payload
- Normalize email address
- Validate email verification status

**Interface**:
```python
class GoogleProfileExtractor:
    @staticmethod
    def extract_profile(token_payload: dict) -> dict:
        """
        Extract user profile from validated token payload.
        
        Args:
            token_payload: Validated ID token payload
        
        Returns:
            dict: {
                'google_id': str,
                'email': str,
                'full_name': str,
                'profile_picture_url': str,
                'email_verified': bool
            }
        
        Raises:
            ValueError: If email is not verified
        """
        # 1. Extract sub (Google user ID)
        # 2. Extract and normalize email
        # 3. Validate email_verified is True
        # 4. Extract name
        # 5. Extract picture URL
        # 6. Return profile dict
```

### 5. Repository: User Management

**File**: `models/user.py` (modification)

**Methods**:
```python
@staticmethod
def find_by_google_id(db: Session, google_id: str) -> Optional['User']:
    """Find user by Google ID."""
    return db.query(User).filter(User.google_id == google_id).first()

@staticmethod
def find_by_email(db: Session, email: str) -> Optional['User']:
    """Find user by email address."""
    return db.query(User).filter(User.email == email).first()

@staticmethod
def create_from_google(db: Session, profile: dict) -> 'User':
    """
    Create new user from Google profile.
    
    Args:
        db: Database session
        profile: Profile dict from ProfileExtractor
    
    Returns:
        User: Newly created user
    """
    # 1. Generate unique username from email
    # 2. Set random secure password hash
    # 3. Set google_id, email, full_name, profile_picture_url
    # 4. Set auth_provider = 'google'
    # 5. Add to session and flush
    # 6. Return user

def link_google_account(self, google_id: str, profile_picture_url: str, full_name: str):
    """
    Link Google account to existing user.
    
    Args:
        google_id: Google user ID
        profile_picture_url: Profile picture URL
        full_name: User's full name
    """
    # 1. Set google_id
    # 2. Update profile_picture_url if not set
    # 3. Update full_name if not set
    # 4. Update auth_provider to 'both' if currently 'traditional'
```

### 6. Configuration

**File**: `config.py` (modification)

**New Configuration Variables**:
```python
# ── Google OAuth ──────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "")
```

**Validation** (in `BaseConfig.validate()`):
```python
# Check Google OAuth configuration in production
if app_env == "production":
    if cls.GOOGLE_CLIENT_ID and len(cls.GOOGLE_CLIENT_SECRET) < 32:
        errors.append("GOOGLE_CLIENT_SECRET too short (minimum 32 characters)")
    if cls.GOOGLE_REDIRECT_URI and not cls.GOOGLE_REDIRECT_URI.startswith("https://"):
        errors.append("GOOGLE_REDIRECT_URI must use HTTPS in production")
```

## Data Models

### User Model Extensions

**File**: `models/user.py`

**New Columns**:
```python
# OAuth provider data
google_id           = Column(String(255), unique=True, index=True, nullable=True)
profile_picture_url = Column(String(500), nullable=True)
full_name           = Column(String(255), nullable=True)
auth_provider       = Column(String(20), default='traditional', nullable=False)
# Values: 'traditional', 'google', 'both'
```

**Indexes**:
- Unique index on `google_id` for fast lookups and constraint enforcement
- Regular index on `google_id` for query performance

**Migration File**: `alembic/versions/YYYYMMDDHHMMSS_add_google_oauth_fields.py`

```python
def upgrade():
    op.add_column('users', sa.Column('google_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('profile_picture_url', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('full_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('auth_provider', sa.String(20), nullable=False, server_default='traditional'))
    
    op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)

def downgrade():
    op.drop_index('ix_users_google_id', 'users')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'full_name')
    op.drop_column('users', 'profile_picture_url')
    op.drop_column('users', 'google_id')
```

### Username Generation Logic

When creating accounts from Google OAuth, usernames are generated from email addresses:

**Algorithm**:
1. Extract local part of email (before @)
2. Remove non-alphanumeric characters except underscores
3. Truncate to 30 characters
4. Check for uniqueness
5. If not unique, append numeric suffix (e.g., `john_doe_2`)
6. Retry up to 10 times with incrementing suffix

**Example**:
- Email: `john.doe@gmail.com` → Username: `john_doe`
- Email: `jane+test@example.com` → Username: `jane_test`
- Collision: `john_doe` exists → Try `john_doe_2`, `john_doe_3`, etc.

## API Endpoints

### POST /auth/google/callback

**Purpose**: Handle Google OAuth callback and create/link user account

**Authentication**: None (public endpoint)

**Rate Limiting**: 5 requests per IP per 60 seconds

**Request Headers**:
```
Content-Type: application/json
```

**Request Body**:
```json
{
  "credential": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "csrf_token": "abc123..."
}
```

**Success Response** (200 OK):
```json
{
  "success": true,
  "redirect_url": "/dashboard"
}
```

**Error Responses**:

**400 Bad Request** - Invalid request:
```json
{
  "success": false,
  "error": "INVALID_REQUEST",
  "message": "Missing credential"
}
```

**403 Forbidden** - CSRF validation failed:
```json
{
  "success": false,
  "error": "CSRF_ERROR",
  "message": "Session expired. Please refresh and try again."
}
```

**429 Too Many Requests** - Rate limit exceeded:
```json
{
  "success": false,
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many authentication attempts. Please wait and try again."
}
```

**401 Unauthorized** - Token validation failed:
```json
{
  "success": false,
  "error": "INVALID_TOKEN",
  "message": "Authentication failed. Please try again."
}
```

**409 Conflict** - Account linking conflict:
```json
{
  "success": false,
  "error": "ACCOUNT_CONFLICT",
  "message": "This email is already linked to a different Google account."
}
```

**500 Internal Server Error** - Server error:
```json
{
  "success": false,
  "error": "INTERNAL_ERROR",
  "message": "An error occurred. Please try again later."
}
```

### GET /auth/google/config

**Purpose**: Provide Google OAuth client configuration to frontend

**Authentication**: None (public endpoint)

**Response** (200 OK):
```json
{
  "enabled": true,
  "client_id": "123456789-abcdefg.apps.googleusercontent.com"
}
```

If OAuth not configured:
```json
{
  "enabled": false
}
```

## Security Considerations

### 1. Token Validation

**Threat**: Forged or tampered ID tokens
**Mitigation**:
- Verify token signature using Google's public keys (fetched from `https://www.googleapis.com/oauth2/v3/certs`)
- Validate `aud` claim matches our client ID
- Validate `iss` claim is `accounts.google.com` or `https://accounts.google.com`
- Validate `exp` claim (token not expired)
- Use official `google-auth` library for validation (battle-tested implementation)

### 2. No Token Storage

**Threat**: Token theft from database breach
**Mitigation**:
- Never store access tokens or refresh tokens in database
- Only store Google user ID (`sub` claim) for future authentication
- ID token is validated once and discarded
- If user needs to re-authenticate, they go through OAuth flow again

### 3. Email Verification Requirement

**Threat**: Account takeover via unverified email
**Mitigation**:
- Check `email_verified` claim in ID token
- Reject authentication if email is not verified
- Display clear error message to user

### 4. Rate Limiting

**Threat**: Brute force attacks, credential stuffing
**Mitigation**:
- Apply rate limiting to `/auth/google/callback` endpoint
- Limit: 5 requests per IP per 60 seconds
- Use existing `check_rate_limit` service with `critical=True` (fail closed on DB errors)
- Log rate limit violations for security monitoring

### 5. CSRF Protection

**Threat**: Cross-site request forgery
**Mitigation**:
- Validate CSRF token on callback endpoint
- Use existing `is_valid_csrf_token` function
- Return 403 Forbidden if CSRF validation fails

### 6. Session Security

**Threat**: Session fixation, session hijacking
**Mitigation**:
- Use existing `_regenerate_session_secure` function
- Bind session to IP address and User-Agent
- Generate new CSRF token on session creation
- Set session as permanent with configured lifetime

### 7. Account Linking Security

**Threat**: Account takeover via email collision
**Mitigation**:
- Check if email already exists before creating account
- If email exists with different Google ID, reject linking
- If email exists without Google ID, link accounts
- Log all account linking events for audit trail

### 8. HTTPS Enforcement

**Threat**: Man-in-the-middle attacks
**Mitigation**:
- Require HTTPS for redirect URI in production
- Validate in `config.py` validation method
- Google OAuth requires HTTPS for production redirect URIs

### 9. Audit Logging

**Threat**: Insufficient visibility into authentication events
**Mitigation**:
- Log all OAuth authentication attempts (success and failure)
- Log account creation and linking events
- Include IP address, user ID, and email in audit logs
- Never log tokens or secrets

### 10. Random Password for OAuth Accounts

**Threat**: Password-based login bypass for OAuth-only accounts
**Mitigation**:
- Generate cryptographically secure random password hash for OAuth accounts
- Use `secrets.token_urlsafe(32)` for password generation
- Hash with bcrypt (13 rounds) before storage
- User cannot login with password unless they explicitly set one via password reset

## Error Handling

### Error Categories

**1. Client Errors (4xx)**
- Invalid request format
- Missing required fields
- CSRF validation failure
- Rate limit exceeded
- Invalid or expired token
- Unverified email
- Account linking conflict

**2. Server Errors (5xx)**
- Database connection failure
- Google API unavailable
- Token validation service error
- Unexpected exceptions

### Error Response Format

All errors follow consistent JSON format:
```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "User-friendly error message"
}
```

### User-Facing Error Messages

**Principle**: Never expose technical details to users

**Examples**:
- ❌ "JWT signature verification failed"
- ✅ "Authentication failed. Please try again."

- ❌ "Database connection timeout"
- ✅ "An error occurred. Please try again later."

- ❌ "Token audience mismatch: expected X, got Y"
- ✅ "Authentication failed. Please try again."

### Error Logging

**Server-Side Logging**:
- Log full technical details for debugging
- Include stack traces for unexpected errors
- Never log tokens or secrets
- Use structured logging with context

**Example**:
```python
logger.error(
    "Google OAuth token validation failed | error=%s | ip=%s",
    str(e),
    client_ip(),
    exc_info=True
)
```

### Frontend Error Handling

**Display Strategy**:
- Show user-friendly error message in flash message
- Provide actionable guidance (e.g., "Please try again" or "Verify your email")
- Allow user to retry OAuth flow
- Provide fallback to traditional registration

**Example**:
```javascript
if (!response.success) {
  showError(response.message);
  enableRetry();
}
```

### Graceful Degradation

**Scenario**: Google OAuth not configured

**Behavior**:
- `/auth/google/config` returns `{"enabled": false}`
- Frontend does not render Google Sign-In button
- Traditional registration remains fully functional
- No error messages shown to user

**Scenario**: Google API temporarily unavailable

**Behavior**:
- Return 500 error with generic message
- Log detailed error server-side
- User can retry or use traditional registration
- System remains operational for existing sessions

## Testing Strategy

### Unit Tests

**Token Validator Tests** (`tests/services/test_google_oauth.py`):
- Valid token validation succeeds
- Invalid signature rejected
- Expired token rejected
- Wrong audience rejected
- Wrong issuer rejected
- Missing claims rejected

**Profile Extractor Tests** (`tests/services/test_google_oauth.py`):
- Valid profile extraction succeeds
- Unverified email rejected
- Missing required fields handled
- Email normalization works correctly

**User Repository Tests** (`tests/models/test_user.py`):
- Create user from Google profile
- Generate unique username from email
- Handle username collisions with numeric suffix
- Link Google account to existing user
- Reject linking to account with different Google ID
- Find user by Google ID
- Find user by email

**Username Generation Tests** (`tests/models/test_user.py`):
- Extract username from email local part
- Remove special characters except underscores
- Truncate to 30 characters
- Handle collisions with numeric suffix
- Retry up to 10 times

### Integration Tests

**OAuth Flow Tests** (`tests/integration/test_google_oauth.py`):
- Complete OAuth flow creates new account
- Complete OAuth flow links existing account
- Session created after successful authentication
- User redirected to dashboard
- CSRF validation enforced
- Rate limiting enforced

**Account Linking Tests** (`tests/integration/test_google_oauth.py`):
- Link Google to existing traditional account
- Reject linking to account with different Google ID
- Update auth_provider to 'both' after linking
- Existing user can login with both methods after linking

**Error Handling Tests** (`tests/integration/test_google_oauth.py`):
- Invalid token returns 401
- Unverified email returns 401
- Missing CSRF token returns 403
- Rate limit exceeded returns 429
- Database error returns 500

### Property-Based Tests

Property-based tests will be written after completing the prework analysis in the Correctness Properties section below.

### Manual Testing Checklist

- [ ] Google Sign-In button appears on registration page
- [ ] Clicking button redirects to Google OAuth
- [ ] Successful authentication creates account and redirects to dashboard
- [ ] Existing email links to Google account
- [ ] Session persists across page refreshes
- [ ] Logout clears session
- [ ] Rate limiting triggers after 5 attempts
- [ ] CSRF validation prevents forged requests
- [ ] Unverified email shows error message
- [ ] Invalid token shows error message
- [ ] Google OAuth disabled when not configured
- [ ] Audit logs capture all OAuth events

### Test Data

**Mock ID Token Payload**:
```python
{
    "iss": "https://accounts.google.com",
    "azp": "123456789-abcdefg.apps.googleusercontent.com",
    "aud": "123456789-abcdefg.apps.googleusercontent.com",
    "sub": "1234567890",
    "email": "test@example.com",
    "email_verified": True,
    "name": "Test User",
    "picture": "https://lh3.googleusercontent.com/a/default-user",
    "given_name": "Test",
    "family_name": "User",
    "iat": 1234567890,
    "exp": 1234571490
}
```

**Test Users**:
- New user (no existing account)
- Existing user with traditional auth
- Existing user with Google auth
- Existing user with both auth methods



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified several areas of redundancy:

**Token Validation Properties (2.4-2.9)**: These can be consolidated into a single comprehensive token validation property that covers signature, audience, issuer, and expiration checks.

**Profile Extraction Properties (3.1-3.3)**: These three separate extraction properties can be combined into one property that validates all required fields are extracted.

**Session Data Properties (5.2-5.7)**: These individual session field properties can be consolidated into a single property that validates the complete session structure.

**Token Storage Properties (6.1-6.2)**: These two properties about not storing tokens can be combined into one comprehensive property.

**Audit Logging Properties (9.1-9.6)**: These can be consolidated into fewer properties that cover logging for all event types while ensuring no sensitive data is logged.

The following properties represent the unique, non-redundant validation requirements:

### Property 1: Token Validation Completeness

*For any* ID token received from Google OAuth, the token validator should verify the signature using Google's public keys, validate that the audience matches our client ID, validate that the issuer is accounts.google.com, and validate that the token has not expired. If any validation check fails, the token should be rejected.

**Validates: Requirements 2.4, 2.7, 2.8, 2.9**

### Property 2: Invalid Token Rejection

*For any* invalid or malformed ID token, the system should reject the authentication attempt, return an appropriate error response, and log the failure without exposing technical details to the user.

**Validates: Requirements 2.5, 2.10, 8.3**

### Property 3: Profile Extraction Completeness

*For any* validated ID token, the profile extractor should successfully extract the email address, full name, and profile picture URL from the token claims, and all extracted values should be non-empty strings.

**Validates: Requirements 3.1, 3.2, 3.3**

### Property 4: Email Verification Requirement

*For any* ID token where the email_verified claim is false, the system should reject the authentication attempt and display an error message requesting email verification.

**Validates: Requirements 3.4**

### Property 5: Email Normalization

*For any* email address extracted from an ID token, the email should be normalized to lowercase before storage or comparison.

**Validates: Requirements 3.5**

### Property 6: Account Creation for New Users

*For any* Google authentication where no existing account matches the Google ID or email, the system should create a new user account with the Google email, a generated unique username, the Google user ID, profile picture URL, full name, auth_provider set to 'google', and a random secure password hash.

**Validates: Requirements 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9**

### Property 7: Username Generation Uniqueness

*For any* email address, the username generation algorithm should produce a unique username by extracting the local part, removing special characters except underscores, truncating to 30 characters, and appending a numeric suffix if a collision is detected.

**Validates: Requirements 4.4**

### Property 8: Account Linking for Existing Users

*For any* Google authentication where an existing account matches the email but has no Google ID, the system should link the Google user ID to the existing account, update the profile picture URL and full name if not already set, and update the auth_provider to 'both'.

**Validates: Requirements 4.2, 11.2, 11.3**

### Property 9: Account Linking Conflict Prevention

*For any* Google authentication where an existing account matches the email but is already linked to a different Google ID, the system should reject the authentication attempt and return an error indicating the account conflict.

**Validates: Requirements 11.1, 11.5**

### Property 10: Session Creation Completeness

*For any* successful Google authentication, the session manager should create a new session using the secure session regeneration function, store the user ID and username, bind the session to the client IP address and User-Agent, set the session as permanent with the configured lifetime, and generate a new CSRF token.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**

### Property 11: Session Validation Consistency

*For any* authenticated session, the session validation logic should apply the same security checks (IP binding, User-Agent binding, CSRF validation) regardless of whether the account was created via traditional registration or Google OAuth.

**Validates: Requirements 5.8, 11.4**

### Property 12: No Token Storage

*For any* Google authentication, the system should never store the OAuth access token or refresh token in the database. Only the Google user ID (sub claim) should be persisted.

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 13: Authentication Failure Logging

*For any* authentication failure (invalid token, unverified email, rate limit exceeded, etc.), the system should log the event with the failure reason and client IP address, but should never log OAuth tokens or client secrets.

**Validates: Requirements 8.5, 9.3, 9.6**

### Property 14: Authentication Success Logging

*For any* successful Google authentication, the system should log the event with the user ID, email address, and client IP address. If a new account was created, it should log an account creation event. If an existing account was linked, it should log an account linking event.

**Validates: Requirements 9.1, 9.2, 9.4, 9.5**

### Property 15: Traditional Registration Preservation

*For any* user interaction with the registration page after adding Google OAuth, the traditional registration form should remain fully functional and unchanged, allowing users to register with username, email, and password.

**Validates: Requirements 1.4**

### Property 16: Graceful Degradation

*For any* deployment where GOOGLE_CLIENT_ID is not configured, the registration page should not display the Google Sign-In button, and the traditional registration flow should remain fully functional without errors.

**Validates: Requirements 6.6, 12.4**

### Property 17: Rate Limiting Enforcement

*For any* IP address that makes more than 5 requests to the OAuth callback endpoint within 60 seconds, the system should reject subsequent requests with an HTTP 429 error and log the rate limit violation.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

### Property 18: Error Recovery

*For any* Google authentication failure, the registration page should display a user-friendly error message and allow the user to retry the OAuth flow or use traditional registration.

**Validates: Requirements 8.6**


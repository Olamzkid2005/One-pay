# OnePay Test Suite

This directory contains the test suite for OnePay, including tests for the Google OAuth integration feature.

## Test Structure

```
tests/
├── __init__.py
├── services/
│   ├── __init__.py
│   └── test_google_oauth.py          # Unit tests for OAuth services
├── models/
│   ├── __init__.py
│   └── test_user_oauth.py            # Unit tests for User OAuth methods
├── integration/
│   ├── __init__.py
│   ├── test_google_oauth_flow.py     # Integration tests for OAuth flow
│   └── test_google_oauth_errors.py   # Error handling tests
├── MANUAL_TESTING_CHECKLIST.md       # Manual testing checklist
└── README.md                          # This file
```

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install pytest pytest-mock
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
# OAuth service tests
pytest tests/services/test_google_oauth.py

# User model OAuth tests
pytest tests/models/test_user_oauth.py

# Integration tests
pytest tests/integration/

# Error handling tests
pytest tests/integration/test_google_oauth_errors.py
```

### Run Tests by Category

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only OAuth-related tests
pytest -m oauth
```

### Run Tests with Coverage

```bash
pip install pytest-cov
pytest --cov=services --cov=models --cov=blueprints --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Run Tests in Verbose Mode

```bash
pytest -v
```

### Run Tests with Output

```bash
pytest -s  # Show print statements
```

## Test Coverage

### Google OAuth Service Layer

**File:** `tests/services/test_google_oauth.py`

Tests for `GoogleTokenValidator` and `GoogleProfileExtractor` classes:

- ✅ Token validation completeness (Property 1)
- ✅ Invalid token rejection (Property 2)
- ✅ Profile extraction completeness (Property 3)
- ✅ Email verification requirement (Property 4)
- ✅ Email normalization (Property 5)
- ✅ Signature verification
- ✅ Audience validation
- ✅ Issuer validation
- ✅ Expiration validation
- ✅ Error message wrapping

### User Model OAuth Methods

**File:** `tests/models/test_user_oauth.py`

Tests for User model OAuth functionality:

- ✅ Username generation uniqueness (Property 7)
- ✅ Account creation for new users (Property 6)
- ✅ Account linking for existing users (Property 8)
- ✅ Account linking conflict prevention (Property 9)
- ✅ Special character handling
- ✅ Username truncation
- ✅ Collision handling with numeric suffix
- ✅ Random password generation
- ✅ Profile data storage

### OAuth Flow Integration Tests

**File:** `tests/integration/test_google_oauth_flow.py`

End-to-end tests for OAuth authentication flow:

- ✅ Complete OAuth flow creates new account
- ✅ Complete OAuth flow links existing account
- ✅ Session creation completeness (Property 10)
- ✅ Session validation consistency (Property 11)
- ✅ No token storage (Property 12)
- ✅ Authentication failure logging (Property 13)
- ✅ Authentication success logging (Property 14)
- ✅ Rate limiting enforcement (Property 17)
- ✅ CSRF validation
- ✅ Account linking conflict rejection
- ✅ Graceful degradation (Property 16)

### Error Handling Tests

**File:** `tests/integration/test_google_oauth_errors.py`

Tests for error scenarios:

- ✅ Invalid token returns 401
- ✅ Unverified email returns 401
- ✅ Missing CSRF token returns 403
- ✅ Invalid CSRF token returns 403
- ✅ Rate limit exceeded returns 429
- ✅ Missing credential returns 400
- ✅ Invalid content type returns 415
- ✅ User-friendly error messages (Property 18)
- ✅ Server error returns 500
- ✅ OAuth not configured returns 503

## Manual Testing

For manual testing scenarios, see:

**File:** `tests/MANUAL_TESTING_CHECKLIST.md`

This checklist covers:
- Traditional registration preservation (Property 15)
- Graceful degradation (Property 16)
- Complete OAuth flows
- Session persistence
- Rate limiting
- CSRF protection
- Audit logging
- Security verification
- Browser compatibility
- Mobile responsiveness

## Correctness Properties

The test suite validates 18 correctness properties defined in the design document:

1. **Token Validation Completeness** - Signature, audience, issuer, expiration
2. **Invalid Token Rejection** - Proper error handling for invalid tokens
3. **Profile Extraction Completeness** - All required fields extracted
4. **Email Verification Requirement** - Unverified emails rejected
5. **Email Normalization** - Emails normalized to lowercase
6. **Account Creation for New Users** - Complete account setup
7. **Username Generation Uniqueness** - Collision-free usernames
8. **Account Linking for Existing Users** - Proper linking logic
9. **Account Linking Conflict Prevention** - Conflicts detected and rejected
10. **Session Creation Completeness** - All session fields set
11. **Session Validation Consistency** - Same validation for all auth methods
12. **No Token Storage** - Only Google ID stored, no tokens
13. **Authentication Failure Logging** - Failures logged securely
14. **Authentication Success Logging** - Successes logged with details
15. **Traditional Registration Preservation** - No regressions
16. **Graceful Degradation** - Works without OAuth configuration
17. **Rate Limiting Enforcement** - Rate limits applied correctly
18. **Error Recovery** - Users can retry after errors

## Continuous Integration

To run tests in CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-mock pytest-cov
    pytest --cov --cov-report=xml
```

## Troubleshooting

### Import Errors

If you get import errors, ensure you're running pytest from the project root:

```bash
cd /path/to/onepay
pytest
```

Or add the project root to PYTHONPATH:

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/onepay"
pytest
```

### Mock Errors

If mocks aren't working, ensure `pytest-mock` is installed:

```bash
pip install pytest-mock
```

### Database Errors

Integration tests use mocked database connections. If you encounter database errors, ensure mocks are properly configured in the test setup.

## Contributing

When adding new tests:

1. Follow existing test structure and naming conventions
2. Use descriptive test names that explain what is being tested
3. Include docstrings referencing correctness properties
4. Mock external dependencies (database, Google API, etc.)
5. Test both success and failure scenarios
6. Update this README with new test coverage

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-Mock Documentation](https://pytest-mock.readthedocs.io/)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [OnePay Design Document](.kiro/specs/google-oauth-integration/design.md)

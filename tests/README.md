# OnePay Tests

This directory contains test files for the OnePay application.

## Test Files

- `test_app.py` - Application and API endpoint tests
- `test_migration.py` - Database migration tests

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run specific test file
```bash
pytest tests/test_app.py
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html tests/
```

### Run with verbose output
```bash
pytest -v tests/
```

## Test Structure

Tests should follow these conventions:
- Test files named `test_*.py`
- Test functions named `test_*`
- Use fixtures for common setup
- Mock external services (Quickteller, email)
- Test both success and failure cases

## Adding New Tests

When adding new features, ensure you add corresponding tests:

1. **Unit Tests** - Test individual functions and methods
2. **Integration Tests** - Test API endpoints and workflows
3. **Security Tests** - Test authentication, authorization, and input validation

## Test Coverage Goals

- Overall coverage: 80%+
- Critical paths (payment flow): 95%+
- Security functions: 100%

## Mocking External Services

Use the mock mode for Quickteller:
```python
app.config['QUICKTELLER_MOCK_MODE'] = True
```

## Test Database

Tests should use a separate test database:
```python
app.config['DATABASE_URL'] = 'sqlite:///test_onepay.db'
```

## Continuous Integration

Tests are automatically run on:
- Pull requests
- Commits to main branch
- Before deployment

## Troubleshooting

If tests fail:
1. Check database migrations are up to date
2. Verify environment variables are set correctly
3. Ensure all dependencies are installed
4. Check for port conflicts if running integration tests

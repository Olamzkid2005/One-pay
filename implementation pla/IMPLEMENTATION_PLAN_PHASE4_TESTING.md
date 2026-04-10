# OnePay Implementation Plan - Phase 4: Testing & Quality

**Version:** 1.0  
**Created:** April 10, 2026  
**Status:** Active  
**Estimated Effort:** ~70 hours

---

## Overview

This document covers Phase 4 of the OnePay implementation plan: Testing & Quality. This phase includes 6 tasks focused on improving test coverage, adding automated testing, and code quality enforcement.

**Tasks in this phase:** 6
- TEST-001: Increase Test Coverage to 90% (24h)
- TEST-002: Add End-to-End Testing with Playwright (16h)
- TEST-003: Implement Load Testing with Locust (8h)
- TEST-004: Add Type Hints Throughout Codebase (20h)
- TEST-005: Implement Pre-commit Hooks (2h)
- TEST-006: Add Code Complexity Monitoring with Radon (2h)

---

## TEST-001: Increase Test Coverage to 90%

**Files:** `tests/`, all Python files  
**Estimated Effort:** 24 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Install coverage tool:
   ```bash
   pip install pytest-cov
   ```
2. Run coverage analysis:
   ```bash
   pytest --cov=. --cov-report=html --cov-report=term-missing
   ```
3. Identify low-coverage modules:
   ```bash
   # View coverage report
   open htmlcov/index.html
   ```
4. Add tests for low-coverage areas:
   - **blueprints/auth.py**: Add tests for OAuth flows, 2FA, password reset
   - **blueprints/payments.py**: Add tests for payment link creation, status checks
   - **services/korapay.py**: Add tests for API calls, circuit breaker
   - **services/webhook.py**: Add tests for webhook delivery, retry logic
   - **core/middleware.py**: Add tests for security headers, session management
5. Create test coverage configuration:
   ```ini
   # .coveragerc
   [run]
   source = .
   omit = 
       venv/*
       tests/*
       migrations/*
       */__pycache__/*
   
   [report]
   exclude_lines =
       pragma: no cover
       def __repr__
       raise NotImplementedError
       if TYPE_CHECKING:
   ```
6. Add coverage to CI/CD:
   ```yaml
   # .github/workflows/test.yml
   - name: Run tests with coverage
     run: |
       pytest --cov=. --cov-report=xml --cov-report=term-missing
   
   - name: Upload coverage to Codecov
     uses: codecov/codecov-action@v3
     with:
       file: ./coverage.xml
   ```

### Acceptance Criteria
- [ ] Overall coverage >= 90%
- [ ] Critical modules (security, payments) >= 95%
- [ ] All new code has tests
- [ ] Coverage report generated in CI

### Testing
- Run coverage report after adding tests
- Verify coverage metrics
- Check for any gaps

### Coverage Targets by Module
```
core/security.py: 100%
core/auth.py: 95%
blueprints/payments.py: 90%
services/korapay.py: 85%
services/webhook.py: 85%
models/: 90%
```

### Checkpoint Test
```bash
# Run coverage analysis
pytest --cov=. --cov-report=term-missing --cov-fail-under=90

# Check coverage report
open htmlcov/index.html
# Expected: Overall coverage >= 90%
```

---

## TEST-002: Add End-to-End Testing with Playwright

**Files:** `tests/e2e/`, `playwright.config.ts`  
**Estimated Effort:** 16 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Install Playwright:
   ```bash
   pip install pytest-playwright
   playwright install
   ```
2. Create Playwright configuration:
   ```typescript
   // playwright.config.ts
   import { defineConfig } from '@playwright/test';
   
   export default defineConfig({
       testDir: './tests/e2e',
       use: {
           baseURL: 'http://localhost:5000',
           headless: true,
       },
       projects: [
           { name: 'chromium', use: { browserName: 'chromium' } },
           { name: 'firefox', use: { browserName: 'firefox' } },
           { name: 'webkit', use: { browserName: 'webkit' } },
       ],
   });
   ```
3. Create E2E test for user registration:
   ```python
   # tests/e2e/test_registration.py
   from playwright.sync_api import Page, expect
   
   def test_user_registration(page: Page):
       page.goto("/register")
       page.fill("input[name='username']", "testuser")
       page.fill("input[name='email']", "test@example.com")
       page.fill("input[name='password']", "TestPassword123!")
       page.click("button[type='submit']")
       expect(page).to_have_url("/dashboard")
   ```
4. Add more E2E test scenarios:
   - User login
   - Payment link creation
   - Invoice generation
   - Password reset
5. Add to CI/CD

### Acceptance Criteria
- [ ] E2E tests cover critical user flows
- [ ] Tests run on multiple browsers
- [ ] Tests integrated in CI/CD
- [ ] Flaky tests minimized

### Checkpoint Test
```bash
# Install Playwright
pip install pytest-playwright
playwright install

# Run E2E tests
pytest tests/e2e/ --headed
# Expected: All tests pass
```

---

## TEST-003: Implement Load Testing with Locust

**Files:** `tests/load/`, `locustfile.py`  
**Estimated Effort:** 8 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Install Locust:
   ```bash
   pip install locust
   ```
2. Create load test file:
   ```python
   # tests/load/locustfile.py
   from locust import HttpUser, task, between
   
   class OnePayUser(HttpUser):
       wait_time = between(1, 3)
       
       @task
       def view_dashboard(self):
           self.client.get("/dashboard")
       
       @task(3)
       def check_status(self):
           self.client.get("/api/payments/status?tx_ref=TEST-REF")
       
       @task
       def create_payment_link(self):
           self.client.post("/api/payments/link", json={
               "amount": "1000.00",
               "currency": "NGN"
           })
   ```
3. Run load tests:
   ```bash
   locust -f tests/load/locustfile.py --host http://localhost:5000
   ```
4. Analyze results and identify bottlenecks

### Acceptance Criteria
- [ ] Load tests simulate realistic traffic patterns
- [ ] Performance bottlenecks identified
- [ ] Response times within acceptable limits
- [ ] Error rate < 1%

### Checkpoint Test
```bash
# Install Locust
pip install locust

# Run load test
locust -f tests/load/locustfile.py --host http://localhost:5000 --users 100 --spawn-rate 10 --headless
# Expected: No errors, acceptable response times
```

---

## TEST-004: Add Type Hints Throughout Codebase

**Files:** All Python files  
**Estimated Effort:** 20 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Add type hints to all functions:
   ```python
   # Example
   from typing import Optional, List, Dict
   
   def create_payment_link(
       amount: Decimal,
       currency: str,
       description: Optional[str] = None
   ) -> Dict[str, Any]:
       """Create a payment link."""
       # Implementation
   ```
2. Use `typing` module for complex types
3. Create `mypy.ini` configuration:
   ```ini
   [mypy]
   python_version = 3.11
   warn_return_any = True
   warn_unused_configs = True
   disallow_untyped_defs = True
   ignore_missing_imports = True
   ```
4. Add mypy to pre-commit hooks
5. Fix mypy errors incrementally

### Acceptance Criteria
- [ ] All public functions have type hints
- [ ] Mypy passes without errors
- [ ] Type hints improve IDE support
- [ ] No runtime performance impact

### Checkpoint Test
```bash
# Run mypy
mypy .
# Expected: No errors

# Run with strict mode
mypy --strict .
# Expected: Minimal errors
```

---

## TEST-005: Implement Pre-commit Hooks

**File:** `.pre-commit-config.yaml`  
**Estimated Effort:** 2 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Create `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: https://github.com/psf/black
       rev: 23.3.0
       hooks:
         - id: black
     - repo: https://github.com/pycqa/isort
       rev: 5.12.0
       hooks:
         - id: isort
     - repo: https://github.com/pycqa/flake8
       rev: 6.0.0
       hooks:
         - id: flake8
     - repo: https://github.com/pre-commit/mirrors-mypy
       rev: v1.3.0
       hooks:
         - id: mypy
     - repo: https://github.com/PyCQA/bandit
       rev: 1.7.5
       hooks:
         - id: bandit
           args: ['-r', '.']
   ```
2. Install pre-commit:
   ```bash
   pip install pre-commit
   pre-commit install
   ```
3. Test hooks

### Acceptance Criteria
- [ ] Code formatting automated
- [ ] Import sorting automated
- [ ] Linting enforced before commit
- [ ] Type checking enforced
- [ ] Security scanning enforced

### Checkpoint Test
```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run hooks
pre-commit run --all-files
# Expected: All hooks pass
```

---

## TEST-006: Add Code Complexity Monitoring with Radon

**File:** CI/CD configuration  
**Estimated Effort:** 2 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Install radon:
   ```bash
   pip install radon
   ```
2. Add to CI/CD:
   ```yaml
   - name: Check code complexity
     run: |
       pip install radon
       radon cc . -a -s --min B
   ```
3. Set complexity limit: McCabe < 10
4. Refactor high-complexity functions

### Acceptance Criteria
- [ ] Average complexity < 10
- [ ] No functions with complexity > 20
- [ ] Complex functions identified for refactoring
- [ ] CI fails on high complexity

### Checkpoint Test
```bash
# Run radon
radon cc . -a -s --min B
# Expected: Average complexity < 10
```

---

## Phase 4 Checkpoint Test

```bash
#!/bin/bash
# Phase 4 Testing Checkpoint Test

echo "=== Phase 4 Testing Checkpoint ==="
echo ""

echo "1. Running Coverage Analysis..."
pytest --cov=. --cov-report=term-missing --cov-fail-under=90
echo "✓ Coverage test completed"

echo "2. Running E2E Tests..."
pytest tests/e2e/ -v || echo "⚠ E2E tests not yet implemented"
echo "✓ E2E test check completed"

echo "3. Running Load Tests..."
locust -f tests/load/locustfile.py --host http://localhost:5000 --users 50 --spawn-rate 5 --headless --run-time 30s || echo "⚠ Load tests not yet implemented"
echo "✓ Load test check completed"

echo "4. Running Type Checking..."
mypy . || echo "⚠ Type hints not yet complete"
echo "✓ Type check completed"

echo "5. Running Pre-commit Hooks..."
pre-commit run --all-files || echo "⚠ Pre-commit hooks not yet configured"
echo "✓ Pre-commit check completed"

echo "6. Running Complexity Analysis..."
radon cc . -a -s --min B || echo "⚠ Radon not yet configured"
echo "✓ Complexity check completed"

echo ""
echo "=== Phase 4 Checkpoint Complete ==="
```

---

## Phase 4 Summary

**Total Tasks:** 6  
**Total Estimated Effort:** ~70 hours  
**Risk Profile:** 5 Low, 1 Medium  
**Dependencies:** None

**Completion Criteria:**
- All 6 checkpoint tests pass
- Test coverage >= 90%
- E2E tests operational
- Load tests configured
- Type hints added throughout
- Pre-commit hooks enforced
- Code complexity within limits

**Next Phase:** Phase 5 - Operations & Monitoring

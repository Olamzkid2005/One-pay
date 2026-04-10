# OnePay Implementation Plan - Phase 1: Security Enhancements

**Version:** 1.0  
**Created:** April 10, 2026  
**Status:** Active  
**Estimated Effort:** ~50 hours

---

## Overview

This document covers Phase 1 of the OnePay implementation plan: Critical Security Enhancements. This phase includes 9 tasks focused on improving the security posture of the application.

**Tasks in this phase:** 9
- SEC-001: Add HSTS Preload Header (2h)
- SEC-002: Add Clear-Site-Data Header for Logout (2h)
- SEC-003: Enhance Permissions-Policy Header (2h)
- SEC-004: Create security.txt File (1h)
- SEC-005: Expand Common Password List (3h)
- SEC-006: Add CAPTCHA to Password Reset (6h)
- SEC-007: Implement Flask-Session with Redis (8h)
- SEC-008: Add Alert Integration for Security Monitoring (10h)
- SEC-009: Implement Automated Security Scanning in CI/CD (6h)

---

## SEC-001: Add HSTS Preload Header

**File:** `core/middleware.py` (lines ~200-250)  
**Estimated Effort:** 2 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Modify `add_security_headers` function in `core/middleware.py`
2. Update existing HSTS header from:
   ```python
   "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
   ```
   to:
   ```python
   "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"
   ```
3. Add configuration option in `config.py`:
   ```python
   HSTS_PRELOAD: bool = os.getenv("HSTS_PRELOAD", "true").lower() == "true"
   ```
4. Update `.env.example` and `.env.production.example` with HSTS_PRELOAD setting

### Acceptance Criteria
- [ ] HSTS header includes `preload` directive in production
- [ ] Header can be disabled via environment variable for testing
- [ ] Application passes securityheaders.com test with A+ rating

### Testing
- Unit test: `test/unit/test_security_headers.py` - verify HSTS preload presence
- Integration test: `test/integration/test_security_headers.py` - verify header in HTTP response

### Checkpoint Test
```bash
# Verify HSTS preload header
curl -I https://localhost:5000 | grep Strict-Transport-Security
# Expected: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

# Run unit tests
pytest tests/unit/test_security_headers.py -v

# Run integration tests
pytest tests/integration/test_security_headers.py -v
```

---

## SEC-002: Add Clear-Site-Data Header for Logout

**File:** `blueprints/auth.py` (logout route)  
**Estimated Effort:** 2 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Modify `/logout` route in `blueprints/auth.py`
2. Add Clear-Site-Data header before session clearing:
   ```python
   @app.route("/logout", methods=["POST"])
   @login_required
   def logout():
       response = redirect(url_for("auth.login"))
       response.headers["Clear-Site-Data"] = "cache, cookies, storage, executionContexts"
       logout_user()
       return response
   ```
3. Update CSRF protection to work with header
4. Add configuration option in `config.py`:
   ```python
   CLEAR_SITE_DATA_ENABLED: bool = os.getenv("CLEAR_SITE_DATA_ENABLED", "true").lower() == "true"
   ```

### Acceptance Criteria
- [ ] Clear-Site-Data header sent on logout
- [ ] Browser cache and storage cleared after logout
- [ ] Can be disabled via environment variable
- [ ] Session properly invalidated

### Testing
- Unit test: `test/unit/test_logout.py` - verify header presence
- Manual test: Logout and verify browser cache cleared

### Checkpoint Test
```bash
# Test logout flow and verify header
curl -X POST http://localhost:5000/logout -i | grep Clear-Site-Data
# Expected: Clear-Site-Data: cache, cookies, storage, executionContexts

# Run unit tests
pytest tests/unit/test_logout.py -v
```

---

## SEC-003: Enhance Permissions-Policy Header

**File:** `core/middleware.py` (lines ~220-230)  
**Estimated Effort:** 2 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Update existing Permissions-Policy header in `core/middleware.py`
2. Current header:
   ```python
   "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=(), usb=()"
   ```
3. Enhanced header:
   ```python
   "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=(), usb=(), "
                         "magnetometer=(), gyroscope=(), accelerometer=(), "
                         "ambient-light-sensor=(), autoplay=(), encrypted-media=(), "
                         "picture-in-picture=(), sync-xhr=(), fullscreen=(), "
                         "interest-cohort=()"
   ```
4. Add configuration in `config.py` for per-directive control

### Acceptance Criteria
- [ ] All additional directives added to header
- [ ] Directives can be configured via environment variables
- [ ] No impact on existing functionality

### Testing
- Unit test: Verify header format and directives
- Integration test: Check header in HTTP response

### Checkpoint Test
```bash
# Verify Permissions-Policy header
curl -I http://localhost:5000 | grep Permissions-Policy
# Expected: All directives present

# Run unit tests
pytest tests/unit/test_security_headers.py -v -k permissions
```

---

## SEC-004: Create security.txt File

**File:** `static/.well-known/security.txt`  
**Estimated Effort:** 1 hour  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Create directory: `static/.well-known/`
2. Create file `static/.well-known/security.txt`:
   ```
   Contact: mailto:security@yourdomain.com
   Expires: 2027-04-10T23:00:00.000Z
   Encryption: https://yourdomain.com/pgp-key.txt
   Acknowledgments: https://yourdomain.com/hall-of-fame
   Preferred-Languages: en
   Policy: https://yourdomain.com/security-policy
   Hiring: https://yourdomain.com/jobs
   ```
3. Add route in `blueprints/public.py`:
   ```python
   @app.route("/.well-known/security.txt")
   def security_txt():
       return send_from_directory("static/.well-known", "security.txt")
   ```
4. Update `docs/SECURITY.md` with disclosure policy

### Acceptance Criteria
- [ ] File accessible at `/.well-known/security.txt`
- [ ] Content follows RFC 9116 standard
- [ ] Expires date updated annually
- [ ] Contact email functional

### Testing
```bash
# Verify security.txt is accessible
curl https://yourdomain.com/.well-known/security.txt
# Expected: Returns security.txt content
```

### Checkpoint Test
```bash
# Test security.txt endpoint
curl http://localhost:5000/.well-known/security.txt
# Expected: Returns security.txt content

# Verify RFC 9116 compliance
# (Manual verification of content format)
```

---

## SEC-005: Expand Common Password List

**File:** `services/validation/password.py` (or create new file)  
**Estimated Effort:** 3 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Download RockYou.txt password list (14M passwords)
2. Filter to top 10,000 most common passwords
3. Create file `services/validation/common_passwords.txt`:
   ```
   password
   123456
   12345678
   qwerty
   ...
   ```
4. Load into set at application startup in `services/validation/password.py`:
   ```python
   def load_common_passwords():
       with open("services/validation/common_passwords.txt") as f:
           return set(line.strip() for line in f)
   
   COMMON_PASSWORDS = load_common_passwords()
   ```
5. Update validation function to check against expanded list
6. Add configuration option for custom password list path

### Acceptance Criteria
- [ ] 10,000 most common passwords blocked
- [ ] Validation performance not degraded (<50ms)
- [ ] Memory usage increase acceptable (<10MB)
- [ ] Custom password list can be specified

### Testing
- Unit test: Verify common passwords rejected
- Performance test: Measure validation time with expanded list

### Performance Optimization
```python
# Use Bloom filter for memory efficiency
from pybloom_live import ScalableBloomFilter

COMMON_PASSWORDS_FILTER = ScalableBloomFilter(initial_capacity=10000, error_rate=0.001)
for password in load_common_passwords():
    COMMON_PASSWORDS_FILTER.add(password)
```

### Checkpoint Test
```bash
# Test password validation with common passwords
python -c "
from services.validation.password import COMMON_PASSWORDS
print('Loaded', len(COMMON_PASSWORDS), 'common passwords')
print('password' in COMMON_PASSWORDS)  # Should be True
"

# Performance test
python -c "
import time
from services.validation.password import is_common_password
start = time.time()
for _ in range(1000):
    is_common_password('password123')
print('Average time:', (time.time() - start) / 1000 * 1000, 'ms')
# Expected: < 50ms
"

# Run unit tests
pytest tests/unit/test_password_validation.py -v
```

---

## SEC-006: Add CAPTCHA to Password Reset

**Files:** `blueprints/auth.py`, `templates/reset_password.html`  
**Estimated Effort:** 6 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Add dependency to `requirements.txt`:
   ```
   hcaptcha==0.1.0
   ```
2. Add configuration to `config.py`:
   ```python
   HCAPTCHA_SITE_KEY: str = os.getenv("HCAPTCHA_SITE_KEY")
   HCAPTCHA_SECRET_KEY: str = os.getenv("HCAPTCHA_SECRET_KEY")
   ```
3. Add hCaptcha widget to `templates/reset_password.html`:
   ```html
   <div class="h-captcha" data-sitekey="{{ config.HCAPTCHA_SITE_KEY }}"></div>
   <script src="https://js.hcaptcha.com/1/api.js" async defer></script>
   ```
4. Update password reset route in `blueprints/auth.py`:
   ```python
   @app.route("/reset-password", methods=["POST"])
   def reset_password():
       token = request.form.get("token")
       captcha_token = request.form.get("h-captcha-response")
       
       # Verify CAPTCHA
       if not verify_captcha(captcha_token):
           flash("CAPTCHA verification failed", "error")
           return redirect(url_for("auth.reset_password_request"))
       
       # Existing password reset logic
   ```
5. Add CAPTCHA verification function:
   ```python
   def verify_captcha(token):
       response = requests.post(
           "https://hcaptcha.com/siteverify",
           data={"secret": Config.HCAPTCHA_SECRET_KEY, "response": token}
       )
       return response.json().get("success", False)
   ```

### Acceptance Criteria
- [ ] CAPTCHA displayed on password reset form
- [ ] CAPTCHA verification required before reset
- [ ] Can be disabled for testing
- [ ] Rate limiting still enforced

### Testing
- Unit test: Verify CAPTCHA verification logic
- Integration test: Test password reset with valid/invalid CAPTCHA
- Manual test: Complete password reset flow

### Configuration
```bash
# .env.example
HCAPTCHA_SITE_KEY=your-site-key
HCAPTCHA_SECRET_KEY=your-secret-key
```

### Checkpoint Test
```bash
# Install dependency
pip install hcaptcha==0.1.0

# Set test environment variables
export HCAPTCHA_SITE_KEY=test-site-key
export HCAPTCHA_SECRET_KEY=test-secret-key

# Run unit tests
pytest tests/unit/test_captcha.py -v

# Manual test: Visit password reset page and verify CAPTCHA displayed
# curl http://localhost:5000/reset-password | grep h-captcha
```

---

## SEC-007: Implement Flask-Session with Redis

**Files:** `config.py`, `core/middleware.py`, `requirements.txt`, `app.py`  
**Estimated Effort:** 8 hours  
**Dependencies:** PERF-004 (Redis cluster support recommended first)  
**Risk:** Medium

### Implementation Steps

1. Add dependencies to `requirements.txt`:
   ```
   Flask-Session==0.5.0
   redis==5.0.0
   ```
2. Add configuration to `config.py`:
   ```python
   SESSION_TYPE: str = "redis"
   SESSION_REDIS: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
   SESSION_KEY_PREFIX: str = "onepay:session:"
   SESSION_USE_SIGNER: bool = True
   SESSION_PERMANENT: bool = False
   SESSION_COOKIE_HTTPONLY: bool = True
   SESSION_COOKIE_SECURE: bool = not Config.DEBUG
   SESSION_COOKIE_SAMESITE: str = "Lax"
   ```
3. Initialize Flask-Session in `app.py`:
   ```python
   from flask_session import Session
   
   Session(app)
   ```
4. Remove session binding to IP/User-Agent (now handled by Redis)
5. Add session cleanup task to `services/task_queue.py`:
   ```python
   @huey.periodic_task(crontab(hour="*/6"))
   def cleanup_expired_sessions():
       """Clean up expired Redis sessions every 6 hours"""
       redis_client = redis.from_url(Config.SESSION_REDIS)
       session_count = redis_client.dbsize()
       logger.info(f"Current Redis sessions: {session_count}")
   ```

### Migration Steps
1. Deploy Redis instance
2. Update configuration
3. Deploy new code
4. Existing sessions will expire naturally (no migration needed)

### Acceptance Criteria
- [ ] Sessions stored in Redis
- [ ] Session data persists across application restarts
- [ ] Multiple application instances share sessions
- [ ] Session expiry handled by Redis TTL
- [ ] Fallback to file-based sessions if Redis unavailable

### Testing
- Integration test: Verify session storage in Redis
- Load test: Test session handling under concurrent load
- Failover test: Test behavior when Redis unavailable

### Rollback Plan
- Set `SESSION_TYPE = "filesystem"` in config
- Sessions stored in `/flask_session/` directory

### Checkpoint Test
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Set environment variables
export REDIS_URL=redis://localhost:6379/0
export SESSION_TYPE=redis

# Run integration tests
pytest tests/integration/test_session_storage.py -v

# Test session persistence
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from flask_session import Session
    print('Flask-Session initialized')
"

# Verify Redis has sessions
redis-cli
> KEYS onepay:session:*
# Expected: Session keys present after login
```

---

## SEC-008: Add Alert Integration for Security Monitoring

**Files:** `services/alerts.py` (new), `config.py`, `services/security_monitor.py`  
**Estimated Effort:** 10 hours  
**Dependencies:** SEC-007 (Redis for queue)  
**Risk:** Medium

### Implementation Steps

1. Add dependencies to `requirements.txt`:
   ```
   slack-sdk==3.26.0
   pagerduty==3.0.0
   sendgrid==6.10.0
   ```
2. Create `services/alerts.py`:
   ```python
   import requests
   from slack_sdk import WebhookClient
   from sendgrid import SendGridAPIClient
   from sendgrid.helpers.mail import Mail
   
   class AlertManager:
       def __init__(self):
           self.slack_webhook = Config.SLACK_WEBHOOK_URL
           self.pagerduty_key = Config.PAGERDUTY_API_KEY
           self.sendgrid_api_key = Config.SENDGRID_API_KEY
       
       def send_slack_alert(self, message, severity="INFO"):
           """Send alert to Slack"""
           client = WebhookClient(self.slack_webhook)
           client.send(text=f"[{severity}] {message}")
       
       def send_pagerduty_alert(self, event, severity):
           """Trigger PagerDuty alert"""
           # Implementation
           pass
       
       def send_email_alert(self, subject, body):
           """Send email alert"""
           message = Mail(
               from_email=Config.MAIL_FROM,
               to_emails=Config.SECURITY_ALERT_EMAIL,
               subject=subject,
               html_content=body
           )
           sg = SendGridAPIClient(self.sendgrid_api_key)
           sg.send(message)
   ```
3. Update `services/security_monitor.py` to use alerts:
   ```python
   from services.alerts import AlertManager
   
   alert_manager = AlertManager()
   
   def detect_suspicious_activity():
       # Existing detection logic
       if alert_level == "CRITICAL":
           alert_manager.send_slack_alert(message, "CRITICAL")
           alert_manager.send_pagerduty_alert(event, "critical")
       elif alert_level == "HIGH":
           alert_manager.send_slack_alert(message, "HIGH")
           alert_manager.send_email_alert(f"Security Alert: {event}", body)
   ```
4. Add configuration to `config.py`:
   ```python
   SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL")
   PAGERDUTY_API_KEY: str = os.getenv("PAGERDUTY_API_KEY")
   PAGERDUTY_SERVICE_ID: str = os.getenv("PAGERDUTY_SERVICE_ID")
   SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY")
   SECURITY_ALERT_EMAIL: str = os.getenv("SECURITY_ALERT_EMAIL", "security@yourdomain.com")
   ```

### Acceptance Criteria
- [ ] Critical alerts sent to Slack and PagerDuty
- [ ] High alerts sent to Slack and email
- [ ] Medium alerts logged only
- [ ] Alert rate limiting to prevent spam
- [ ] Alert delivery failures logged

### Testing
- Unit test: Verify alert sending logic
- Integration test: Test alert delivery to each channel
- Load test: Verify alert rate limiting

### Configuration
```bash
# .env.production.example
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
PAGERDUTY_API_KEY=your-api-key
PAGERDUTY_SERVICE_ID=your-service-id
SENDGRID_API_KEY=your-sendgrid-key
SECURITY_ALERT_EMAIL=security@yourdomain.com
```

### Checkpoint Test
```bash
# Install dependencies
pip install slack-sdk pagerduty sendgrid

# Set test environment variables
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/test
export SENDGRID_API_KEY=test-key
export SECURITY_ALERT_EMAIL=test@example.com

# Run unit tests
pytest tests/unit/test_alerts.py -v

# Test Slack alert (manual)
python -c "
from services.alerts import AlertManager
manager = AlertManager()
manager.send_slack_alert('Test alert', 'INFO')
"

# Test email alert (manual)
python -c "
from services.alerts import AlertManager
manager = AlertManager()
manager.send_email_alert('Test Subject', 'Test Body')
"
```

---

## SEC-009: Implement Automated Security Scanning in CI/CD

**Files:** `.github/workflows/security.yml` (or `.gitlab-ci.yml`), `.pre-commit-config.yaml`  
**Estimated Effort:** 6 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Create `.github/workflows/security.yml`:
   ```yaml
   name: Security Scan
   
   on:
     push:
       branches: [ main, develop ]
     pull_request:
       branches: [ main ]
     schedule:
       - cron: '0 2 * * *'  # Daily at 2 AM
   
   jobs:
     dependency-scan:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Run Safety
           run: |
             pip install safety
             safety check --json > safety-report.json || true
         - name: Upload Safety Report
           uses: actions/upload-artifact@v3
           with:
             name: safety-report
             path: safety-report.json
     
     sast-scan:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Run Bandit
           run: |
             pip install bandit[toml]
             bandit -r . -f json -o bandit-report.json || true
         - name: Upload Bandit Report
           uses: actions/upload-artifact@v3
           with:
             name: bandit-report
             path: bandit-report.json
     
     container-scan:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Build Docker Image
           run: docker build -t onepay:latest .
         - name: Run Trivy
           uses: aquasecurity/trivy-action@master
           with:
             image-ref: 'onepay:latest'
             format: 'sarif'
             output: 'trivy-results.sarif'
         - name: Upload Trivy Results
           uses: github/codeql-action/upload-sarif@v2
           with:
             sarif_file: 'trivy-results.sarif'
   ```
2. Add pre-commit hook for local scanning:
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/PyCQA/bandit
       rev: 1.7.5
       hooks:
         - id: bandit
           args: ['-r', '.']
     - repo: https://github.com/Lucas-C/pre-commit-hooks-safety
       rev: v1.3.2
       hooks:
         - id: python-safety-dependencies-check
           files: requirements.txt
   ```
3. Add dependency to `requirements.txt`:
   ```
   bandit[toml]==1.7.5
   safety==2.3.5
   trivy==0.40.0
   ```

### Acceptance Criteria
- [ ] Dependency vulnerabilities scanned on every push
- [ ] SAST scan runs on every commit
- [ ] Container image scanned on every build
- [ ] Daily scheduled scan for full vulnerability check
- [ ] Reports uploaded as artifacts
- [ ] Build fails on high/critical vulnerabilities

### Testing
- Trigger workflow manually
- Verify all scans run successfully
- Check artifact uploads

### Configuration
```yaml
# bandit.toml
[bandit]
exclude_dirs = ['/tests', '/venv']
skips = ['B101']  # Skip assert_used
```

### Checkpoint Test
```bash
# Install tools
pip install bandit[toml] safety trivy

# Run Safety locally
safety check

# Run Bandit locally
bandit -r . -f json -o bandit-report.json

# Run Trivy locally
docker build -t onepay:latest .
trivy image onepay:latest

# Install pre-commit
pip install pre-commit
pre-commit install

# Run pre-commit hooks
pre-commit run --all-files

# Verify GitHub Actions workflow syntax (if using GitHub)
# (Manual verification in GitHub UI)
```

---

## Phase 1 Checkpoint Test

Run all Phase 1 security tests to verify completion:

```bash
#!/bin/bash
# Phase 1 Security Checkpoint Test

echo "=== Phase 1 Security Checkpoint Test ==="
echo ""

echo "1. Testing HSTS Preload Header..."
curl -I http://localhost:5000 | grep -q "preload" && echo "✓ HSTS preload present" || echo "✗ HSTS preload missing"

echo "2. Testing Clear-Site-Data Header..."
curl -X POST http://localhost:5000/logout -i 2>/dev/null | grep -q "Clear-Site-Data" && echo "✓ Clear-Site-Data present" || echo "✗ Clear-Site-Data missing"

echo "3. Testing Permissions-Policy Header..."
curl -I http://localhost:5000 | grep -q "magnetometer" && echo "✓ Enhanced Permissions-Policy present" || echo "✗ Enhanced Permissions-Policy missing"

echo "4. Testing security.txt..."
curl -s http://localhost:5000/.well-known/security.txt | grep -q "Contact:" && echo "✓ security.txt accessible" || echo "✗ security.txt missing"

echo "5. Testing Common Password List..."
python -c "from services.validation.password import COMMON_PASSWORDS; print('✓ Loaded', len(COMMON_PASSWORDS), 'passwords')" 2>/dev/null || echo "✗ Common password list not loaded"

echo "6. Testing CAPTCHA..."
curl -s http://localhost:5000/reset-password | grep -q "h-captcha" && echo "✓ CAPTCHA widget present" || echo "✗ CAPTCHA widget missing"

echo "7. Testing Redis Session Storage..."
redis-cli KEYS "onepay:session:*" | wc -l | grep -q "[1-9]" && echo "✓ Redis sessions present" || echo "⚠ No Redis sessions (may need login)"

echo "8. Testing Alert Manager..."
python -c "from services.alerts import AlertManager; print('✓ AlertManager importable')" 2>/dev/null || echo "✗ AlertManager not importable"

echo "9. Running Security Scans..."
safety check > /dev/null 2>&1 && echo "✓ Safety scan passed" || echo "✗ Safety scan failed"
bandit -r . -q > /dev/null 2>&1 && echo "✓ Bandit scan passed" || echo "✗ Bandit scan failed"

echo ""
echo "=== Phase 1 Checkpoint Complete ==="
```

---

## Phase 1 Summary

**Total Tasks:** 9  
**Total Estimated Effort:** ~50 hours  
**Risk Profile:** 6 Low, 2 Medium, 1 High  
**Dependencies:** 1 internal (SEC-007 depends on PERF-004)

**Completion Criteria:**
- All 9 checkpoint tests pass
- Security headers verified
- Security scans passing in CI/CD
- Alert system functional
- Redis session storage operational

**Next Phase:** Phase 2 - Performance & Scalability

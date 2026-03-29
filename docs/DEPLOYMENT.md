# OnePay Production Deployment Guide

**Version:** 1.2.5  
**Last Updated:** March 29, 2026  
**Status:** Production Ready ✅

---

## Security Status

**OnePay v1.2.5 Security Posture:**
- ✅ 16/18 vulnerabilities resolved (89%)
- ✅ 0 Critical vulnerabilities remaining
- ✅ 0 High severity vulnerabilities remaining
- ✅ 0 Medium severity vulnerabilities remaining
- ✅ 24/24 security tests passing

**Key Security Features:**
- Session binding (IP + User-Agent)
- SSRF protection (webhook blacklist)
- Security monitoring (5-minute intervals)
- Password strength validation
- Audit log retention (90 days)
- Production hardening (SQLite blocked, secrets validated)

See [SECURITY.md](SECURITY.md) for complete security documentation.

---

## Pre-Deployment Requirements

### 1. Database Migration ✅ REQUIRED

```bash
# 1. Backup current database
cp onepay.db onepay.db.backup.$(date +%Y%m%d)

# 2. Run migration
alembic upgrade head

# 3. Verify migration
alembic current
# Should show: 20260322195525 (head)

# 4. Test database integrity
python -c "from database import get_db; from models.transaction import Transaction; \
with get_db() as db: print(f'Transactions: {db.query(Transaction).count()}')"
```

### 2. Environment Configuration

Create `.env.production` with strong secrets:

```bash
# Generate strong secrets (REQUIRED - 32+ characters each)
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('HMAC_SECRET=' + secrets.token_hex(32))"
python -c "import secrets; print('WEBHOOK_SECRET=' + secrets.token_hex(32))"

# CRITICAL: All three secrets MUST be different!
# Application will refuse to start if secrets are weak or identical

# Required variables
APP_ENV=production
DEBUG=false
SECRET_KEY=<generated-above-32+chars>
HMAC_SECRET=<generated-above-32+chars-DIFFERENT>
WEBHOOK_SECRET=<generated-above-32+chars-DIFFERENT>
ENFORCE_HTTPS=true

# Database (PostgreSQL REQUIRED in production - SQLite will cause startup failure)
DATABASE_URL=postgresql://user:password@localhost/onepay

# Quickteller credentials
QUICKTELLER_CLIENT_ID=<your-client-id>
QUICKTELLER_CLIENT_SECRET=<your-client-secret>
MERCHANT_CODE=<your-merchant-code>
PAYABLE_CODE=<your-payable-code>

# Email configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=<your-email>
MAIL_PASSWORD=<your-app-password>
MAIL_FROM=noreply@yourdomain.com

# Rate limiting (adjust based on expected traffic)
RATE_LIMIT_LINK_CREATE=10
RATE_LIMIT_VERIFY=20
RATE_LIMIT_VERIFY_PAGE_ATTEMPTS=5

# Session configuration
SESSION_LIFETIME_HOURS=24
SESSION_TIMEOUT_AUTHENTICATED=30
SESSION_TIMEOUT_UNAUTHENTICATED=60

# Link expiration (minutes)
LINK_EXPIRATION_MINUTES=30

# Webhook configuration
WEBHOOK_TIMEOUT_SECS=10
WEBHOOK_MAX_RETRIES=3
```

**Security Validation:**
The application will automatically validate on startup and refuse to start if:
- Secrets contain "change-this" placeholder text
- Secrets are shorter than 32 characters
- SECRET_KEY and HMAC_SECRET are identical
- WEBHOOK_SECRET and HMAC_SECRET are identical
- DEBUG=true in production
- ENFORCE_HTTPS=false in production
- SQLite is used in production (PostgreSQL required)

### 3. Security Validation

Run the security validation script:

```bash
# This will validate all security requirements
python -c "from config import Config; Config.validate()"
```

**Expected Output:** Should exit cleanly with no errors.

**If validation fails, you'll see errors like:**
```
STARTUP ABORTED: Security validation failed:
  - SECRET_KEY contains placeholder value
  - HMAC_SECRET too short (minimum 32 characters)
  - SQLite not allowed in production (use PostgreSQL)
```

**Security Validation Checks:**
- ✅ Secrets don't contain "change-this" placeholder
- ✅ Secrets are 32+ characters (256+ bits entropy)
- ✅ SECRET_KEY and HMAC_SECRET are different
- ✅ WEBHOOK_SECRET and HMAC_SECRET are different
- ✅ DEBUG=false in production
- ✅ ENFORCE_HTTPS=true in production
- ✅ PostgreSQL configured (not SQLite)

### 4. Database Migration

```bash
# Run all migrations including security enhancements
alembic upgrade head

# Verify migration completed
alembic current
# Should show: 20260329135018 (head)

# Verify webhook_blacklist table created
python -c "from models.webhook_blacklist import WebhookBlacklist; \
from database import get_db; \
with get_db() as db: print(f'Webhook blacklist table: OK')"
```

### 5. Security Test Suite

Run the comprehensive security validation:

```bash
# Run all security tests
python test_final_security_validation.py

# Expected output:
# ================================================================================
# FINAL SECURITY VALIDATION TEST SUITE
# Testing all 16 resolved vulnerabilities
# ================================================================================
# 
# CRITICAL VULNERABILITIES (3)
# ✓ VULN-001: Secret validation enforced unconditionally
# ✓ VULN-002: Session binding to IP and User-Agent implemented
# ✓ VULN-003: Webhook blacklist prevents DNS rebinding
# 
# [... all tests passing ...]
# 
# ✅ ALL SECURITY VALIDATIONS PASSED
# 🎉 Application is PRODUCTION READY
```

## Testing Checklist

### Critical Security Tests

- [ ] **Secret Validation Test**
  ```bash
  # Test with weak secret - should fail
  SECRET_KEY=weak HMAC_SECRET=weak python app.py
  # Expected: STARTUP ABORTED: Security validation failed
  
  # Test with placeholder - should fail
  SECRET_KEY=change-this-in-production python app.py
  # Expected: STARTUP ABORTED: SECRET_KEY contains placeholder value
  
  # Test with SQLite in production - should fail
  APP_ENV=production DATABASE_URL=sqlite:///test.db python app.py
  # Expected: STARTUP ABORTED: SQLite not allowed in production
  ```

- [ ] **Session Binding Test**
  ```bash
  # Login and capture session cookie
  # Change IP or User-Agent
  # Verify session is invalidated
  # Expected: Redirected to login with "Session IP mismatch" in logs
  ```

- [ ] **Webhook Blacklist Test**
  ```bash
  # Set webhook URL to internal IP
  curl -X POST http://localhost:5000/api/settings/webhook \
    -H "Content-Type: application/json" \
    -d '{"webhook_url": "http://127.0.0.1/webhook"}'
  # Expected: URL rejected or blacklisted on delivery attempt
  ```

- [ ] **Password Strength Test**
  ```bash
  # Try to register with weak password
  # Expected: "Password must be at least 12 characters"
  
  # Try common password
  # Expected: "This password is too common"
  ```

- [ ] **Security Monitoring Test**
  ```bash
  # Check logs for security monitoring thread
  grep "Security monitoring thread started" /var/log/onepay/error.log
  # Expected: Thread started message
  
  # Trigger brute force detection (50+ failed logins)
  # Expected: "SECURITY ALERT: Distributed brute force detected" in logs
  ```

- [ ] **XSS Protection Test**
  ```bash
  # Create transaction with XSS payload in description
  curl -X POST http://localhost:5000/api/payments/link \
    -H "Content-Type: application/json" \
    -H "X-CSRFToken: <token>" \
    -d '{"amount": 1000, "description": "<script>alert(1)</script>"}'
  # Verify script is escaped in history page
  ```

- [ ] **CSRF Protection Test**
  ```bash
  # Try login without CSRF token
  curl -X POST http://localhost:5000/login \
    -d "username=test&password=test"
  # Should fail with CSRF error
  ```

- [ ] **Session Fixation Test**
  1. Get CSRF token before login
  2. Login with valid credentials
  3. Verify CSRF token changed after login

- [ ] **Error Handler Test**
  ```bash
  # Test 404
  curl http://localhost:5000/nonexistent
  # Should return friendly error, not stack trace
  
  # Test 500 (trigger intentional error)
  # Verify no stack trace exposed
  ```

### Functional Tests

- [ ] **User Registration**
  - Register new user
  - Verify email validation
  - Verify password requirements
  - Check rate limiting (3 attempts per hour)

- [ ] **User Login**
  - Login with valid credentials
  - Test account lockout (5 failed attempts)
  - Verify session persistence
  - Test logout

- [ ] **Payment Link Creation**
  - Create payment link
  - Verify virtual account generated
  - Check idempotency (same key returns same link)
  - Test rate limiting (10 per minute)

- [ ] **Payment Verification**
  - Open payment link
  - Verify countdown timer works
  - Test polling (should auto-confirm in mock mode)
  - Verify success state displays correctly
  - Test expired link handling

- [ ] **Transaction History**
  - View transaction history
  - Test pagination
  - Export CSV
  - Verify no XSS in descriptions

- [ ] **Webhook Delivery**
  - Set webhook URL in settings
  - Complete payment
  - Verify webhook delivered
  - Check webhook signature

- [ ] **Password Reset**
  - Request password reset
  - Verify email sent
  - Reset password with token
  - Verify old token invalidated

### Performance Tests

- [ ] **Load Test**
  ```bash
  # Test 100 concurrent users
  ab -n 1000 -c 100 http://localhost:5000/
  # Monitor response times and error rate
  ```

- [ ] **Database Performance**
  ```bash
  # Check query performance
  # Enable SQL logging and review slow queries
  ```

- [ ] **Memory Usage**
  ```bash
  # Monitor memory usage under load
  # Check for memory leaks
  ```

---

## Deployment Steps

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv nginx postgresql redis-server

# Create application user
sudo useradd -m -s /bin/bash onepay
sudo su - onepay
```

### 2. Application Deployment

```bash
# Clone repository
git clone <your-repo-url> /home/onepay/app
cd /home/onepay/app

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# Copy production environment file
cp .env.production .env

# Run database migration
alembic upgrade head

# Test application
python app.py
# Should start without errors
```

### 3. Gunicorn Configuration

Create `/home/onepay/app/gunicorn.conf.py`:

```python
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/onepay/access.log"
errorlog = "/var/log/onepay/error.log"
loglevel = "info"

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
```

### 4. Systemd Service

Create `/etc/systemd/system/onepay.service`:

```ini
[Unit]
Description=OnePay Payment Application
After=network.target postgresql.service

[Service]
Type=notify
User=onepay
Group=onepay
WorkingDirectory=/home/onepay/app
Environment="PATH=/home/onepay/app/venv/bin"
ExecStart=/home/onepay/app/venv/bin/gunicorn -c gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable onepay
sudo systemctl start onepay
sudo systemctl status onepay
```

### 5. Nginx Configuration

Create `/etc/nginx/sites-available/onepay`:

```nginx
upstream onepay {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL certificates (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    # Logging
    access_log /var/log/nginx/onepay_access.log;
    error_log /var/log/nginx/onepay_error.log;
    
    # Max upload size
    client_max_body_size 10M;
    
    location / {
        proxy_pass http://onepay;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Static files (if serving directly)
    location /static {
        alias /home/onepay/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/onepay /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. SSL Certificate (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo systemctl reload nginx
```

### 7. Log Rotation

Create `/etc/logrotate.d/onepay`:

```
/var/log/onepay/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 onepay onepay
    sharedscripts
    postrotate
        systemctl reload onepay > /dev/null 2>&1 || true
    endscript
}
```

### 8. Database Backup

Create `/home/onepay/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/onepay/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# PostgreSQL backup
pg_dump -U onepay onepay | gzip > $BACKUP_DIR/onepay_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "onepay_*.sql.gz" -mtime +30 -delete

echo "Backup completed: onepay_$DATE.sql.gz"
```

Add to crontab:

```bash
crontab -e
# Add: 0 2 * * * /home/onepay/backup.sh
```

---

## Monitoring Setup

### 1. Security Monitoring

**Background Thread Status:**
```bash
# Verify security monitoring thread started
grep "Security monitoring thread started" /var/log/onepay/error.log
grep "Webhook retry thread started" /var/log/onepay/error.log

# Monitor security alerts
tail -f /var/log/onepay/error.log | grep "SECURITY ALERT"
```

**Security Events to Monitor:**

**Critical (Immediate Action Required):**
- `STARTUP ABORTED: Security validation failed` - Configuration error
- `DNS rebinding detected` - SSRF attack attempt
- `Webhook blacklisted` - Malicious webhook URL
- `AWS metadata access attempt` - Cloud metadata SSRF

**High Severity (Investigate Within 1 Hour):**
- `Session IP mismatch` - Potential session hijacking
- `Session User-Agent mismatch` - Potential session hijacking
- `SECURITY ALERT: Distributed brute force detected` - Active attack (>50 failed logins/hour)
- `SECURITY ALERT: Unusual link creation volume` - Spam attack (>1000 links/hour)

**Medium Severity (Investigate Within 24 Hours):**
- `SECURITY ALERT: High webhook failure rate` - System issues (>100 failures/hour)
- `SECURITY ALERT: Excessive rate limit violations` - Abuse attempt (>500 hits/hour)

### 2. Health Check Monitoring

```bash
# Add to crontab for health check
*/5 * * * * curl -f http://localhost:8000/health || echo "OnePay health check failed" | mail -s "OnePay Alert" admin@yourdomain.com
```

### 2. Log Monitoring

```bash
# Monitor error logs
sudo tail -f /var/log/onepay/error.log

# Monitor security events
sudo tail -f /var/log/onepay/error.log | grep -E "SECURITY|Session.*mismatch|DNS rebinding"

# Monitor access logs
sudo tail -f /var/log/onepay/access.log

# Monitor nginx logs
sudo tail -f /var/log/nginx/onepay_error.log

# Check for security alerts in last hour
grep "SECURITY ALERT" /var/log/onepay/error.log | grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')"
```

### 3. System Monitoring

Install monitoring tools:

```bash
sudo apt install -y htop iotop nethogs
```

---

## Post-Deployment Verification

### 1. Smoke Tests

```bash
# Test homepage
curl -I https://yourdomain.com
# Should return 200 OK

# Test health endpoint
curl https://yourdomain.com/health
# Should return {"status": "ok", ...}

# Test SSL
curl -I https://yourdomain.com
# Should have HSTS header
```

### 3. Security Scan

```bash
# Run SSL test
https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com
# Target: A+ rating

# Run security headers test
https://securityheaders.com/?q=yourdomain.com
# Target: A rating

# Verify security headers present
curl -I https://yourdomain.com | grep -E "Strict-Transport-Security|X-Frame-Options|Content-Security-Policy"
# Expected: All three headers present
```

### 4. Security Validation

```bash
# Test response time
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.com

# Load test
ab -n 1000 -c 50 https://yourdomain.com/

# Verify security monitoring is active
curl https://yourdomain.com/health | jq '.security_monitoring'
# Expected: "active" or similar indicator
```

---

## Rollback Plan

If issues occur after deployment:

```bash
# 1. Stop application
sudo systemctl stop onepay

# 2. Restore database backup
gunzip < /home/onepay/backups/onepay_YYYYMMDD_HHMMSS.sql.gz | psql -U onepay onepay

# 3. Revert code
cd /home/onepay/app
git checkout <previous-commit>

# 4. Downgrade database
alembic downgrade -1

# 5. Restart application
sudo systemctl start onepay
```

---

## Maintenance Tasks

### Daily
- [ ] Check error logs for security alerts
- [ ] Monitor disk space
- [ ] Verify backups completed
- [ ] Check security monitoring thread status

### Weekly
- [ ] Review transaction volume
- [ ] Check webhook delivery success rate
- [ ] Review security logs and alerts
- [ ] Check webhook blacklist for new entries
- [ ] Review failed login attempts

### Monthly
- [ ] Update dependencies (security patches)
- [ ] Review and rotate logs
- [ ] Test backup restoration
- [ ] Security audit and vulnerability scan
- [ ] Review audit log retention (90 days)
- [ ] Test disaster recovery procedures

---

## Support Contacts

- **Technical Lead:** [Your Name]
- **DevOps:** [DevOps Contact]
- **Security:** [Security Contact]
- **Quickteller Support:** [Interswitch Support]

---

## Completion Sign-off

- [ ] All pre-deployment requirements completed
- [ ] Security validation passed (no weak secrets, PostgreSQL configured)
- [ ] All security tests passed (24/24)
- [ ] Deployment steps completed
- [ ] Security monitoring configured and active
- [ ] Webhook blacklist table created
- [ ] Session binding validated
- [ ] Post-deployment verification passed
- [ ] Security headers verified (A+ SSL Labs, A Security Headers)
- [ ] Team notified of deployment

**Deployed By:** _______________  
**Date:** _______________  
**Version:** 1.2.5  
**Security Status:** Production Ready ✅

---

## Additional Resources

- [Security Documentation](SECURITY.md) - Comprehensive security guide
- [Security Audit Report](../security-reports/2026-03-29-comprehensive-security-audit.md) - Full audit results
- [Security Fixes Summary](FINAL_SECURITY_FIXES_2026-03-29.md) - All resolved vulnerabilities
- [Webhook Verification](WEBHOOK_VERIFICATION.md) - Webhook setup guide
- [Manual Test Guide](MANUAL_TEST_GUIDE.md) - Testing procedures

---

**Status:** ✅ Production Ready - All security requirements met

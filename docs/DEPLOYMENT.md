# OnePay Production Deployment Checklist

**Version:** 1.0  
**Last Updated:** March 22, 2026  
**Status:** Ready for deployment after completing this checklist

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
# Generate strong secrets
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('HMAC_SECRET=' + secrets.token_hex(32))"
python -c "import secrets; print('WEBHOOK_SECRET=' + secrets.token_hex(32))"

# Required variables
APP_ENV=production
SECRET_KEY=<generated-above>
HMAC_SECRET=<generated-above>
WEBHOOK_SECRET=<generated-above>
ENFORCE_HTTPS=true

# Database (use PostgreSQL in production)
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

# Session lifetime (hours)
SESSION_LIFETIME_HOURS=24

# Link expiration (minutes)
LINK_EXPIRATION_MINUTES=30
```

### 3. Security Validation

Run the security validation script:

```bash
python -c "from config import Config; Config.validate()"
```

Should exit cleanly with no errors.

---

## Testing Checklist

### Critical Security Tests

- [ ] **Race Condition Test**
  ```bash
  # Test concurrent payment confirmations
  # Use Apache Bench or similar tool
  ab -n 100 -c 10 http://localhost:5000/api/payments/transfer-status/TX-TEST-123
  # Verify only one confirmation occurs
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

### 1. Health Check Monitoring

```bash
# Add to crontab for health check
*/5 * * * * curl -f http://localhost:8000/health || echo "OnePay health check failed" | mail -s "OnePay Alert" admin@yourdomain.com
```

### 2. Log Monitoring

```bash
# Monitor error logs
sudo tail -f /var/log/onepay/error.log

# Monitor access logs
sudo tail -f /var/log/onepay/access.log

# Monitor nginx logs
sudo tail -f /var/log/nginx/onepay_error.log
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

### 2. Security Scan

```bash
# Run SSL test
https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com
# Target: A+ rating

# Run security headers test
https://securityheaders.com/?q=yourdomain.com
# Target: A rating
```

### 3. Performance Test

```bash
# Test response time
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.com

# Load test
ab -n 1000 -c 50 https://yourdomain.com/
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
- [ ] Check error logs for issues
- [ ] Monitor disk space
- [ ] Verify backups completed

### Weekly
- [ ] Review transaction volume
- [ ] Check webhook delivery success rate
- [ ] Review security logs

### Monthly
- [ ] Update dependencies
- [ ] Review and rotate logs
- [ ] Test backup restoration
- [ ] Security audit

---

## Support Contacts

- **Technical Lead:** [Your Name]
- **DevOps:** [DevOps Contact]
- **Security:** [Security Contact]
- **Quickteller Support:** [Interswitch Support]

---

## Completion Sign-off

- [ ] All pre-deployment requirements completed
- [ ] All tests passed
- [ ] Deployment steps completed
- [ ] Monitoring configured
- [ ] Post-deployment verification passed
- [ ] Team notified of deployment

**Deployed By:** _______________  
**Date:** _______________  
**Version:** _______________

---

**Status:** ✅ Ready for production deployment

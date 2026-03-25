# OnePay Security Documentation

## 🔒 Security Overview

OnePay implements defense-in-depth security with multiple layers of protection:

- **Authentication & Authorization**: Session-based auth with CSRF protection
- **Input Validation**: Server-side validation on all user inputs
- **Rate Limiting**: Database-backed rate limiting on sensitive endpoints
- **Cryptographic Security**: HMAC-SHA256 for payment link integrity
- **Audit Logging**: Comprehensive security event logging
- **HTTPS Enforcement**: Configurable HTTPS-only mode
- **Security Headers**: CSP, HSTS, X-Frame-Options, etc.

---

## 🚨 Critical Security Requirements

### 1. Strong Secrets (MANDATORY)

Generate cryptographically strong secrets before deployment:

```bash
# Generate SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# Generate HMAC_SECRET (must be different from SECRET_KEY)
python -c "import secrets; print('HMAC_SECRET=' + secrets.token_hex(32))"

# Generate WEBHOOK_SECRET (must be different from both above)
python -c "import secrets; print('WEBHOOK_SECRET=' + secrets.token_hex(32))"
```

Add these to your `.env` file. The application will refuse to start in production with placeholder secrets.

### 2. Database Security

**Production**: Use PostgreSQL with SSL/TLS:
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
```

**Never use SQLite in production** - it lacks proper concurrent access controls.

### 3. HTTPS Enforcement

Enable HTTPS in production:
```env
ENFORCE_HTTPS=true
TRUST_X_FORWARDED_PROTO=true  # Only if behind a trusted reverse proxy
```

### 4. Reverse Proxy Configuration

If behind nginx/Cloudflare/AWS ALB:
```env
TRUST_X_FORWARDED_FOR=true
TRUST_X_FORWARDED_PROTO=true
```

**WARNING**: Only enable these if you control the proxy. Untrusted proxies can spoof these headers.

---

## 🛡️ Security Features

### Authentication & Session Management

- **Password Hashing**: PBKDF2-SHA256 via Werkzeug (100,000+ iterations)
- **Password Policy**: Minimum 12 characters with uppercase, lowercase, number, and special character
- **Session Security**: 
  - HttpOnly cookies (prevents XSS theft)
  - SameSite=Lax (prevents CSRF)
  - Secure flag in production (HTTPS-only)
  - 24-hour session lifetime (configurable)
  - Session regeneration on login (prevents fixation)
- **Account Lockout**: 5 failed attempts = 15-minute lockout
- **CSRF Protection**: Token-based protection on all state-changing operations

### Input Validation

All user inputs are validated server-side:

- **Amount**: Decimal validation, max 2 decimal places, range checks, finite number validation
- **Email**: RFC-compliant regex validation
- **Phone**: International format validation
- **URLs**: Whitelist-based validation (HTTPS only, no private IPs)
- **Transaction References**: Alphanumeric format enforcement

### Rate Limiting

Database-backed rate limiting (survives restarts, works across workers):

| Endpoint | Limit | Window |
|----------|-------|--------|
| Login | 5 attempts | 60 seconds |
| Password Reset (IP) | 3 attempts | 5 minutes |
| Password Reset (User) | 2 attempts | 1 hour |
| Password Reset Token Validation | 10 attempts | 5 minutes |
| Create Link | 10 links | 60 seconds |
| Verify Page | 5 views | 5 minutes |
| Transfer Status Poll | 20 polls | 60 seconds |

### Cryptographic Security

- **Payment Links**: HMAC-SHA256 signatures prevent tampering
- **Webhook Signatures**: HMAC-SHA256 for webhook authenticity
- **Token Generation**: `secrets.token_urlsafe()` for reset tokens (48 bytes)
- **Transaction References**: `secrets.token_hex(16)` for unguessable IDs

### SSRF Protection

Webhook URLs are validated to prevent Server-Side Request Forgery:

- ✅ HTTPS only (no HTTP, file://, gopher://, etc.)
- ✅ Public IPs only (blocks 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- ✅ No localhost/loopback (blocks 127.0.0.1, ::1)
- ✅ No credentials in URL (blocks user:pass@host)
- ✅ Redirects disabled in webhook delivery

### Audit Logging

All security-relevant events are logged with 90-day retention:

- `merchant.login` / `merchant.login_failed`
- `merchant.registered`
- `link.created` / `link.reissued`
- `payment.confirmed`
- `webhook.delivered` / `webhook.failed`
- `settings.webhook_updated`

Logs include: user_id, tx_ref, IP address, timestamp, structured detail JSON.

Audit logs are automatically cleaned up after 90 days via the health check endpoint.

### Security Headers

Automatically applied to all responses:

```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; base-uri 'self'; form-action 'self'; ...
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=(), usb=(), magnetometer=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload (HTTPS only)
```

### Webhook Security

- HMAC-SHA256 signatures on all webhooks
- Separate WEBHOOK_SECRET (falls back to HMAC_SECRET)
- Exponential backoff retries (up to 3 attempts)
- SSRF protection on webhook URLs
- Response size limits (1MB max)
- Timeout protection (10 seconds)
- Redirect prevention

**Webhook Verification**: See [WEBHOOK_VERIFICATION.md](WEBHOOK_VERIFICATION.md) for complete implementation examples in Python, Node.js, and PHP.

---

## 🔐 Secure Deployment Checklist

### Pre-Deployment

- [ ] Generate strong secrets (SECRET_KEY, HMAC_SECRET, WEBHOOK_SECRET)
- [ ] Configure PostgreSQL with SSL
- [ ] Set `ENFORCE_HTTPS=true`
- [ ] Configure SMTP for password reset emails
- [ ] Set up Quickteller API credentials (or run in mock mode)
- [ ] Review rate limit settings for your traffic patterns
- [ ] Configure webhook retry settings

### Infrastructure

- [ ] Deploy behind HTTPS reverse proxy (nginx, Cloudflare, AWS ALB)
- [ ] Enable firewall rules (allow 443, block direct access to app port)
- [ ] Set up database backups
- [ ] Configure log aggregation (CloudWatch, Datadog, etc.)
- [ ] Set up monitoring and alerting
- [ ] Implement DDoS protection (Cloudflare, AWS Shield)

### Post-Deployment

- [ ] Test HTTPS enforcement
- [ ] Verify security headers (use securityheaders.com)
- [ ] Test rate limiting
- [ ] Verify webhook signature validation
- [ ] Test password reset flow
- [ ] Review audit logs
- [ ] Set up automated security scanning (Dependabot, Snyk)

---

## 🚨 Incident Response

### Suspected Secret Compromise

1. **Immediately rotate secrets**:
   ```bash
   # Generate new secrets
   python -c "import secrets; print(secrets.token_hex(32))"
   
   # Update .env with new values
   # Keep old HMAC_SECRET as HMAC_SECRET_OLD for 24h grace period
   ```

2. **Invalidate all sessions**: Restart the application
3. **Review audit logs** for suspicious activity
4. **Notify affected users** if data breach occurred

### Suspicious Activity

1. Check audit logs: `SELECT * FROM audit_logs WHERE event LIKE '%failed%' ORDER BY created_at DESC LIMIT 100;`
2. Review rate limit violations in logs
3. Check for unusual transaction patterns
4. Block malicious IPs at firewall level

### Vulnerability Disclosure

Report security vulnerabilities to: [your-security-email@domain.com]

Please include:
- Vulnerability description
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

---

## 🔍 Security Testing

### Manual Testing

```bash
# Test rate limiting
for i in {1..10}; do curl -X POST http://localhost:5000/api/payments/link; done

# Test CSRF protection
curl -X POST http://localhost:5000/api/payments/link \
  -H "Content-Type: application/json" \
  -d '{"amount": 1000}'

# Test SQL injection (should be blocked)
curl "http://localhost:5000/api/payments/status/'; DROP TABLE users; --"

# Test SSRF (should be blocked)
curl -X POST http://localhost:5000/api/account/settings \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "http://169.254.169.254/latest/meta-data/"}'
```

### Automated Security Scanning

```bash
# Dependency vulnerability scanning
pip install safety
safety check -r requirements.txt

# SAST (Static Application Security Testing)
pip install bandit
bandit -r . -ll

# Secrets scanning
pip install detect-secrets
detect-secrets scan
```

---

## 📚 Security Best Practices

### For Developers

1. **Never log sensitive data**: Passwords, tokens, full credit card numbers
2. **Always use parameterized queries**: SQLAlchemy ORM prevents SQL injection
3. **Validate on the server**: Never trust client-side validation
4. **Use constant-time comparison**: `hmac.compare_digest()` for secrets
5. **Fail securely**: Rate limiter fails open, but logs the error
6. **Principle of least privilege**: Database user should have minimal permissions

### For Operators

1. **Keep dependencies updated**: Run `pip list --outdated` weekly
2. **Monitor audit logs**: Set up alerts for failed login spikes
3. **Rotate secrets regularly**: Every 90 days minimum
4. **Backup database daily**: Test restore procedures
5. **Use separate environments**: Dev, staging, production with different secrets
6. **Limit database access**: Only application server should access DB

### For Merchants

1. **Verify webhook signatures**: Always validate X-OnePay-Signature header
2. **Use HTTPS for webhooks**: Never expose webhook endpoints over HTTP
3. **Implement idempotency**: Handle duplicate webhook deliveries gracefully
4. **Store payment links securely**: Don't expose hash tokens in URLs
5. **Monitor for suspicious transactions**: Set up alerts for unusual patterns

---

## 🔄 Security Updates

### Dependency Updates

```bash
# Check for security updates
pip list --outdated

# Update specific package
pip install --upgrade flask

# Update all dependencies (test thoroughly!)
pip install --upgrade -r requirements.txt
```

### Security Patches

Subscribe to security advisories:
- Flask: https://github.com/pallets/flask/security/advisories
- SQLAlchemy: https://github.com/sqlalchemy/sqlalchemy/security/advisories
- Requests: https://github.com/psf/requests/security/advisories

---

## 📞 Support

For security questions or concerns:
- Email: [security@yourdomain.com]
- Documentation: https://github.com/yourorg/onepay/wiki/Security
- Security Policy: https://github.com/yourorg/onepay/security/policy

---

**Last Updated**: 2024-01-01  
**Security Review**: Quarterly  
**Next Review**: 2024-04-01

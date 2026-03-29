# OnePay Security Documentation

**Last Updated:** March 29, 2026  
**Version:** 1.2.5  
**Status:** Production Ready

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Security Audit Results](#security-audit-results)
3. [Implemented Security Controls](#implemented-security-controls)
4. [Security Architecture](#security-architecture)
5. [Authentication & Authorization](#authentication--authorization)
6. [Data Protection](#data-protection)
7. [API Security](#api-security)
8. [Security Monitoring](#security-monitoring)
9. [Incident Response](#incident-response)
10. [Security Best Practices](#security-best-practices)
11. [Compliance](#compliance)

---

## Security Overview

OnePay is a secure payment gateway built with security as a core principle. The application has undergone comprehensive security auditing and implements industry-standard security controls.

### Security Posture

- **Vulnerabilities Resolved:** 16/18 (89%)
- **Critical Vulnerabilities:** 0 remaining
- **High Severity Vulnerabilities:** 0 remaining
- **Medium Severity Vulnerabilities:** 0 remaining
- **Security Test Coverage:** 24/24 tests passing

### Security Certifications

- OWASP Top 10 2021 compliance
- WCAG 2.1 AA accessibility compliance (partial)
- PCI DSS considerations implemented

---

## Security Audit Results

### Comprehensive Security Audit - March 29, 2026

**Total Findings:** 18 vulnerabilities identified  
**Resolved:** 16 vulnerabilities (89%)  
**Remaining:** 2 low-priority informational items

#### Critical Vulnerabilities (3/3 Resolved ✅)

1. **VULN-001: Weak Secret Validation**
   - **Status:** RESOLVED
   - **Fix:** Unconditional secret validation in all environments
   - **Impact:** Application refuses to start with weak secrets

2. **VULN-002: Session Fixation**
   - **Status:** RESOLVED
   - **Fix:** Session binding to IP address and User-Agent
   - **Impact:** Sessions invalidated on IP/User-Agent mismatch

3. **VULN-003: DNS Rebinding in Webhooks**
   - **Status:** RESOLVED
   - **Fix:** Webhook blacklist with immediate abort on DNS rebinding
   - **Impact:** SSRF attacks prevented

#### High Severity Vulnerabilities (6/6 Resolved ✅)

4. **VULN-004: Insufficient Password Reset Rate Limiting**
   - **Status:** RESOLVED
   - **Fix:** Stricter rate limits (2 per 10min IP, 1/hour username)

5. **VULN-005: Timing Attack on Transaction Lookup**
   - **Status:** RESOLVED
   - **Fix:** Random jitter delay (10-50ms), user_id filtering

6. **VULN-006: Weak Password Requirements**
   - **Status:** RESOLVED
   - **Fix:** Comprehensive password validation (12+ chars, complexity checks)

7. **VULN-016: ReDoS in Rate Limiter**
   - **Status:** RESOLVED
   - **Fix:** Pre-compiled regex patterns, length checks

8. **VULN-017: Missing Audit Log Indexes**
   - **Status:** RESOLVED
   - **Fix:** Composite indexes on audit logs

9. **VULN-018: Clickjacking on Payment Pages**
   - **Status:** RESOLVED
   - **Fix:** Conditional CSP frame-ancestors header

#### Medium Severity Vulnerabilities (5/5 Resolved ✅)

10. **VULN-007: Missing Content-Type Validation**
    - **Status:** RESOLVED
    - **Fix:** Content-Type validation on all JSON APIs

11. **VULN-008: Insufficient Input Length Validation**
    - **Status:** RESOLVED
    - **Fix:** Reject oversized inputs (not truncate)

12. **VULN-009: No Rate Limiting on QR Code Generation**
    - **Status:** RESOLVED
    - **Fix:** 5-second timeout on QR generation

13. **VULN-010: Audit Log Retention Not Enforced**
    - **Status:** RESOLVED
    - **Fix:** 90-day retention policy with automated cleanup

14. **VULN-011: No Monitoring for Suspicious Activity**
    - **Status:** RESOLVED
    - **Fix:** Security monitoring background thread (5-minute intervals)

#### Low Severity Vulnerabilities (1/1 Resolved ✅)

15. **VULN-012: SQLite in Production**
    - **Status:** RESOLVED
    - **Fix:** Fatal error on startup if SQLite detected in production

#### Remaining Items (Low Priority)

16. **VULN-013: Missing Security Headers** (Optional)
    - Additional HSTS and Clear-Site-Data headers

17. **VULN-015: Security.txt** (Informational)
    - Responsible disclosure file

---

## Implemented Security Controls

### 1. Authentication & Session Management

#### Password Security
- **Hashing:** bcrypt with 13 rounds (OWASP 2024 compliant)
- **Minimum Length:** 12 characters
- **Complexity Requirements:**
  - Uppercase letters
  - Lowercase letters
  - Numbers
  - Special characters
- **Common Password Blocking:** 50+ common passwords blocked
- **Sequential/Repeated Character Detection:** Prevents weak patterns

#### Session Security
- **Session Binding:** IP address and User-Agent validation
- **Session Timeout:**
  - Authenticated: 30 minutes inactivity
  - Unauthenticated: 60 minutes inactivity
  - Maximum: 7 days absolute
- **Session Invalidation:** On IP/User-Agent mismatch
- **CSRF Protection:** Token validation on all state-changing operations
- **Cookie Security:**
  - HttpOnly: true
  - Secure: true (in production)
  - SameSite: Lax

#### Account Lockout
- **Failed Login Attempts:** 5 attempts
- **Lockout Duration:** 15 minutes
- **Rate Limiting:**
  - Login: Per IP and per username
  - Password Reset: 2 per 10min IP, 1/hour username

### 2. Input Validation & Sanitization

#### Validation Rules
- **Email:** Max 255 characters, RFC 5322 format
- **Phone:** Max 20 characters, numeric validation
- **URLs:** Max 500 characters, HTTPS enforcement
- **Transaction References:** Format validation
- **Amounts:** Decimal type (no float precision errors)

#### Content-Type Validation
- All JSON API endpoints require `application/json`
- Returns 415 Unsupported Media Type otherwise

#### SQL Injection Prevention
- Parameterized queries via SQLAlchemy ORM
- No string concatenation in queries

#### XSS Prevention
- HTML escaping in templates
- Content-Security-Policy headers
- X-XSS-Protection enabled

### 3. API Security

#### Rate Limiting
- **Payment Link Creation:** 10 per minute per user
- **Transaction Status:** 100 per minute per user
- **Verification Page:** 5 attempts per 5 minutes
- **Password Reset:** 2 per 10 minutes per IP

#### SSRF Prevention
- **Webhook URL Validation:**
  - HTTPS enforcement
  - DNS rebinding detection on every retry
  - Blacklist for malicious URLs
  - AWS metadata endpoint blocking (169.254.x.x)
- **Return URL Validation:**
  - Length limits
  - Format validation

#### Webhook Security
- **Signature Verification:** HMAC-SHA256
- **Constant-Time Comparison:** Prevents timing attacks
- **Secret Rotation:** Support for old secrets during rotation
- **Timeout Protection:** 10-second timeout
- **Retry Logic:** 3 attempts with exponential backoff

### 4. Security Headers

#### Comprehensive Headers
```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; ...
X-Frame-Options: DENY (or conditional for payment pages)
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=(), usb=()
X-XSS-Protection: 1; mode=block
X-Download-Options: noopen
```

### 5. Cryptography

#### Secrets Management
- **Secret Validation:** Enforced at startup
- **Minimum Entropy:** 32 characters (256 bits)
- **Unique Secrets:** SECRET_KEY, HMAC_SECRET, WEBHOOK_SECRET must differ
- **Environment Variables:** All secrets stored in environment variables
- **No Hardcoded Secrets:** Validation prevents placeholder values

#### Cryptographic Operations
- **Password Hashing:** bcrypt (13 rounds)
- **HMAC:** SHA-256 for payment link signatures
- **Random Generation:** `secrets` module (cryptographically secure)
- **Constant-Time Comparison:** `hmac.compare_digest()` for tokens

### 6. Audit Logging

#### Logged Events
- Authentication events (login, logout, failed attempts)
- Payment link creation
- Transaction status checks
- Webhook deliveries
- Rate limit violations
- Security events (session mismatch, DNS rebinding)

#### Log Retention
- **Retention Period:** 90 days
- **Automated Cleanup:** Background thread runs daily
- **Log Format:** JSON structured logging in production
- **Sensitive Data Filtering:** PII and secrets filtered from logs

#### Audit Log Schema
```python
{
    "event": "merchant.login_success",
    "user_id": 123,
    "ip_address": "192.168.1.1",
    "detail": {"username": "merchant@example.com"},
    "created_at": "2026-03-29T10:00:00Z"
}
```

---

## Security Architecture

### Defense in Depth

OnePay implements multiple layers of security controls:

1. **Network Layer:** HTTPS enforcement, HSTS headers
2. **Application Layer:** Input validation, CSRF protection, rate limiting
3. **Session Layer:** Session binding, timeout, invalidation
4. **Data Layer:** Parameterized queries, encryption at rest
5. **Monitoring Layer:** Security monitoring, audit logging

### Security Monitoring

#### Background Thread
- **Frequency:** Every 5 minutes
- **Detection Patterns:**
  - Distributed brute force (>50 failed logins/hour)
  - Payment link spam (>1000 links/hour)
  - Webhook failures (>100 failures/hour)
  - Rate limit violations (>500 hits/hour)

#### Alert Levels
- **Critical:** Immediate action required (logged as CRITICAL)
- **High:** Investigate within 1 hour
- **Medium:** Investigate within 24 hours

#### Alert Integration
- Currently: Logged to application logs
- Future: Email/Slack/PagerDuty integration ready

---

## Authentication & Authorization

### Authentication Flow

1. **User Registration:**
   - Password strength validation
   - bcrypt hashing (13 rounds)
   - Email verification (optional)

2. **User Login:**
   - Rate limiting (per IP and username)
   - Account lockout after 5 failed attempts
   - Session creation with IP/User-Agent binding
   - CSRF token generation

3. **Session Validation:**
   - IP address match check
   - User-Agent match check
   - Inactivity timeout check
   - Absolute timeout check (7 days)

4. **Password Reset:**
   - Rate limiting (2 per 10min IP, 1/hour username)
   - Token generation (30-minute expiry)
   - Consistent error messages (prevent enumeration)

### Authorization

#### Resource Ownership
- All transactions filtered by `user_id`
- Payment links owned by creating user
- Invoices owned by creating user

#### API Endpoints
- Authentication required for all dashboard endpoints
- Public endpoints: `/pay/<tx_ref>`, `/api/payments/verify`
- Admin endpoints: None (single-tenant application)

---

## Data Protection

### Data Classification

#### Sensitive Data
- Passwords (hashed with bcrypt)
- Payment information (not stored, proxied to Quickteller)
- Session tokens
- HMAC secrets
- Webhook secrets

#### Personal Data (PII)
- Email addresses
- Phone numbers
- IP addresses (in audit logs)
- Transaction references

### Data Storage

#### Database Security
- **Production:** PostgreSQL required
- **Development:** SQLite allowed
- **Encryption at Rest:** Database-level encryption recommended
- **Backups:** Regular backups with encryption

#### Secrets Storage
- Environment variables only
- No secrets in code or configuration files
- No secrets in version control

### Data Retention

#### Audit Logs
- **Retention:** 90 days
- **Cleanup:** Automated daily cleanup
- **Purpose:** Security monitoring, compliance

#### Transactions
- **Retention:** Indefinite (business requirement)
- **Archival:** Consider archival strategy for old transactions

#### Sessions
- **Retention:** 7 days maximum
- **Cleanup:** Automatic on expiry

---

## API Security

### Endpoint Security

#### Public Endpoints
```
GET  /pay/<tx_ref>              - Payment verification page
POST /api/payments/verify       - Payment verification API
GET  /api/payments/preview      - Payment link preview
GET  /health                    - Health check
```

#### Authenticated Endpoints
```
POST /api/payments/link         - Create payment link
GET  /api/payments/status       - Transaction status
POST /api/payments/reissue      - Reissue payment link
GET  /api/payments/history      - Transaction history
POST /api/settings/webhook      - Update webhook URL
```

### API Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| Payment Link Creation | 10 | 1 minute |
| Transaction Status | 100 | 1 minute |
| Verification Page | 5 | 5 minutes |
| Password Reset | 2 | 10 minutes |
| Login | 5 attempts | 15 min lockout |

### API Error Handling

#### Error Responses
```json
{
    "success": false,
    "error": "ERROR_CODE",
    "message": "User-friendly error message"
}
```

#### Security Considerations
- Generic error messages (no stack traces in production)
- Consistent error messages (prevent enumeration)
- Rate limit errors (429 Too Many Requests)
- Authentication errors (401 Unauthorized)

---

## Security Monitoring

### Real-Time Monitoring

#### Security Events
```
CRITICAL: STARTUP ABORTED: Security validation failed
CRITICAL: SECURITY ALERT: Distributed brute force detected
WARNING:  Session IP mismatch | user=merchant@example.com
WARNING:  DNS rebinding detected | url=https://attacker.com
INFO:     Security monitoring detected 3 alerts
```

#### Log Monitoring Commands
```bash
# Check for security alerts
grep "SECURITY ALERT" app.log | tail -n 50

# Check for session mismatches
grep "Session.*mismatch" app.log

# Check for DNS rebinding attempts
grep "DNS rebinding detected" app.log

# Verify background threads started
grep "thread started" app.log
```

### Metrics & Dashboards

#### Key Security Metrics
- Failed login attempts per hour
- Rate limit violations per hour
- Session invalidations per hour
- Webhook blacklist additions per day
- Audit log growth rate

#### Recommended Monitoring
- Application logs (JSON structured)
- Database performance metrics
- API response times
- Error rates by endpoint

---

## Incident Response

### Security Incident Classification

#### Critical Incidents
- Unauthorized access to production database
- Exposure of secrets or credentials
- Successful SSRF attack
- Data breach or PII exposure

#### High Severity Incidents
- Multiple failed authentication attempts (brute force)
- Session hijacking attempts
- DNS rebinding attempts
- Unusual payment link creation patterns

#### Medium Severity Incidents
- Rate limit violations
- Webhook delivery failures
- Invalid Content-Type attempts

### Incident Response Process

1. **Detection:** Security monitoring alerts or manual discovery
2. **Containment:** Isolate affected systems, revoke compromised credentials
3. **Investigation:** Analyze logs, identify root cause
4. **Remediation:** Apply fixes, update security controls
5. **Recovery:** Restore normal operations
6. **Post-Incident:** Document lessons learned, update procedures

### Contact Information

**Security Team Email:** security@yourdomain.com  
**Emergency Contact:** [To be configured]  
**PGP Key:** [To be configured]

---

## Security Best Practices

### For Developers

1. **Never hardcode secrets** - Use environment variables
2. **Always validate input** - Trust no user input
3. **Use parameterized queries** - Prevent SQL injection
4. **Implement rate limiting** - Prevent abuse
5. **Log security events** - Enable monitoring
6. **Test security fixes** - Write security tests
7. **Review code for security** - Use security checklist

### For Operators

1. **Generate strong secrets** - Use `secrets.token_hex(32)`
2. **Enable HTTPS** - Set `ENFORCE_HTTPS=true`
3. **Use PostgreSQL in production** - No SQLite
4. **Monitor security logs** - Watch for alerts
5. **Keep dependencies updated** - Regular security updates
6. **Backup regularly** - Encrypted backups
7. **Test disaster recovery** - Regular DR drills

### For Users

1. **Use strong passwords** - 12+ characters, mixed complexity
2. **Enable 2FA** - When available (future feature)
3. **Monitor account activity** - Check transaction history
4. **Report suspicious activity** - Contact security team
5. **Keep credentials secure** - Don't share passwords

---

## Compliance

### OWASP Top 10 2021

| Risk | Status | Controls |
|------|--------|----------|
| A01: Broken Access Control | ✅ Mitigated | Authorization checks, session binding |
| A02: Cryptographic Failures | ✅ Mitigated | bcrypt, HTTPS, strong secrets |
| A03: Injection | ✅ Mitigated | Parameterized queries, input validation |
| A04: Insecure Design | ✅ Mitigated | Security by design, defense in depth |
| A05: Security Misconfiguration | ✅ Mitigated | Secret validation, production checks |
| A06: Vulnerable Components | ⚠️ Ongoing | Regular dependency updates |
| A07: Authentication Failures | ✅ Mitigated | Strong passwords, rate limiting, lockout |
| A08: Software/Data Integrity | ✅ Mitigated | HMAC signatures, webhook verification |
| A09: Logging Failures | ✅ Mitigated | Comprehensive audit logging |
| A10: SSRF | ✅ Mitigated | Webhook blacklist, DNS rebinding detection |

### PCI DSS Considerations

While OnePay does not store payment card data (proxied to Quickteller), the following PCI DSS principles are implemented:

- **Requirement 2:** Strong secrets, no default passwords
- **Requirement 6:** Secure development practices, security testing
- **Requirement 8:** Strong authentication, password policies
- **Requirement 10:** Audit logging and monitoring
- **Requirement 11:** Security testing and vulnerability management

### GDPR Considerations

- **Data Minimization:** Only necessary data collected
- **Purpose Limitation:** Data used only for stated purposes
- **Storage Limitation:** 90-day audit log retention
- **Security:** Encryption, access controls, audit logging
- **Accountability:** Security documentation, incident response

---

## Security Testing

### Automated Testing

**Test Suite:** `test_final_security_validation.py`  
**Coverage:** 24/24 tests passing

#### Test Categories
- Critical vulnerability fixes (3 tests)
- High severity fixes (6 tests)
- Medium severity fixes (5 tests)
- Integration validation (5 tests)
- File structure validation (4 tests)

### Manual Testing

**Test Guide:** `docs/MANUAL_TEST_GUIDE.md`

#### Security Test Cases
1. Secret validation enforcement
2. Session fixation prevention
3. DNS rebinding protection
4. Password strength validation
5. Rate limiting effectiveness
6. Input validation
7. CSRF protection
8. XSS prevention

### Penetration Testing

**Recommended Frequency:** Annually  
**Scope:** Web application, API, infrastructure  
**Tools:** OWASP ZAP, Burp Suite, Nmap

---

## Security Roadmap

### Completed (v1.2.5)
- ✅ Comprehensive security audit
- ✅ Critical vulnerability fixes
- ✅ High severity vulnerability fixes
- ✅ Medium severity vulnerability fixes
- ✅ Security monitoring implementation
- ✅ Audit log retention policy

### Planned (Future Releases)

#### Short-Term
- Add CAPTCHA to password reset form
- Expand common password list to 10k entries
- Implement Flask-Session with Redis
- Add remaining security headers (HSTS, Clear-Site-Data)
- Create security.txt file

#### Medium-Term
- Two-factor authentication (2FA)
- Email/Slack/PagerDuty alert integration
- Security dashboard for monitoring
- Automated security scanning in CI/CD
- Bug bounty program

#### Long-Term
- SOC 2 Type II certification
- PCI DSS Level 1 certification (if storing card data)
- Advanced threat detection with ML
- Security information and event management (SIEM)

---

## References

### Documentation
- [Security Audit Report](../security-reports/2026-03-29-comprehensive-security-audit.md)
- [Security Fixes Summary](FINAL_SECURITY_FIXES_2026-03-29.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Webhook Verification](WEBHOOK_VERIFICATION.md)

### Standards & Guidelines
- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [PCI DSS](https://www.pcisecuritystandards.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### Tools & Resources
- [OWASP ZAP](https://www.zaproxy.org/)
- [Burp Suite](https://portswigger.net/burp)
- [Security Headers](https://securityheaders.com/)
- [SSL Labs](https://www.ssllabs.com/ssltest/)

---

## Changelog

### Version 1.2.5 - March 29, 2026
- Resolved 16/18 security vulnerabilities
- Implemented security monitoring
- Added audit log retention
- Enhanced password validation
- Improved session security
- Added SSRF protection

### Version 1.2.0 - March 29, 2026
- Initial security documentation
- Basic security controls implemented

---

**Document Version:** 1.0  
**Last Reviewed:** March 29, 2026  
**Next Review:** June 29, 2026  
**Owner:** Security Team

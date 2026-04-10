# OnePay Implementation Plan - Phase 6: Documentation

**Version:** 1.0  
**Created:** April 10, 2026  
**Status:** Active  
**Estimated Effort:** ~18 hours

---

## Overview

This document covers Phase 6 of the OnePay implementation plan: Documentation. This phase includes 3 tasks focused on improving documentation quality and completeness.

**Tasks in this phase:** 3
- DOC-001: Add API Examples in Multiple Languages (8h)
- DOC-002: Create Architecture Decision Records (ADRs) (6h)
- DOC-003: Add Troubleshooting Guide (4h)

---

## DOC-001: Add API Examples in Multiple Languages

**File:** `docs/API_EXAMPLES.md` (new)  
**Estimated Effort:** 8 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Create `docs/API_EXAMPLES.md` with examples for:
   - Python (requests library)
   - JavaScript (fetch)
   - PHP (cURL)
   - cURL command line

2. Python example:
   ```python
   # Create Payment Link
   import requests
   
   url = "https://api.onepay.com/api/v1/payments/link"
   headers = {
       "Authorization": "Bearer onepay_live_xxxxx",
       "Content-Type": "application/json"
   }
   payload = {
       "amount": "1000.00",
       "currency": "NGN",
       "description": "Payment for order #12345"
   }
   
   response = requests.post(url, json=payload, headers=headers)
   data = response.json()
   
   print(f"Payment Link: {data['data']['payment_url']}")
   print(f"Reference: {data['data']['tx_ref']}")
   ```

3. JavaScript example:
   ```javascript
   // Create Payment Link
   const response = await fetch('https://api.onepay.com/api/v1/payments/link', {
       method: 'POST',
       headers: {
           'Authorization': 'Bearer onepay_live_xxxxx',
           'Content-Type': 'application/json'
       },
       body: JSON.stringify({
           amount: '1000.00',
           currency: 'NGN',
           description: 'Payment for order #12345'
       })
   });
   
   const data = await response.json();
   console.log('Payment Link:', data.data.payment_url);
   console.log('Reference:', data.data.tx_ref);
   ```

4. PHP example:
   ```php
   // Create Payment Link
   $url = 'https://api.onepay.com/api/v1/payments/link';
   $headers = [
       'Authorization: Bearer onepay_live_xxxxx',
       'Content-Type: application/json'
   ];
   $payload = [
       'amount' => '1000.00',
       'currency' => 'NGN',
       'description' => 'Payment for order #12345'
   ];
   
   $ch = curl_init($url);
   curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
   curl_setopt($ch, CURLOPT_POST, true);
   curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
   curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
   
   $response = curl_exec($ch);
   $data = json_decode($response, true);
   
   echo "Payment Link: " . $data['data']['payment_url'] . "\n";
   echo "Reference: " . $data['data']['tx_ref'] . "\n";
   ```

5. cURL example:
   ```bash
   # Create Payment Link
   curl -X POST https://api.onepay.com/api/v1/payments/link \
     -H "Authorization: Bearer onepay_live_xxxxx" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": "1000.00",
       "currency": "NGN",
       "description": "Payment for order #12345"
     }'
   ```

6. Add examples for all major endpoints:
   - Create payment link
   - Check transaction status
   - List invoices
   - Create API key
   - Receive webhooks

### Acceptance Criteria
- [ ] Examples in Python, JavaScript, PHP, cURL
- [ ] All major endpoints covered
- [ ] Error handling examples included
- [ ] Code tested and verified

### Checkpoint Test
```bash
# Verify documentation exists
ls docs/API_EXAMPLES.md
# Expected: File exists

# Test Python example
python -c "
import requests
# Test the example code works
print('Python example syntax valid')
"

# Verify all language examples are present
grep -q "Python" docs/API_EXAMPLES.md
grep -q "JavaScript" docs/API_EXAMPLES.md
grep -q "PHP" docs/API_EXAMPLES.md
grep -q "cURL" docs/API_EXAMPLES.md
```

---

## DOC-002: Create Architecture Decision Records (ADRs)

**Directory:** `docs/adr/`  
**Estimated Effort:** 6 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Create ADR directory:
   ```bash
   mkdir -p docs/adr
   ```

2. Create ADR template:
   ```markdown
   # ADR-XXX: [Title]
   
   ## Status
   Accepted / Proposed / Deprecated / Superseded by [ADR-XXX]
   
   ## Context
   What is the issue that we're seeing that is motivating this decision or change?
   
   ## Decision
   What is the change that we're proposing and/or doing?
   
   ## Consequences
   - What becomes easier or more difficult to do because of this change?
   - What are the trade-offs of this decision?
   
   ## References
   Links to related issues, PRs, or other ADRs.
   ```

3. Create ADR-001: Flask Framework Selection
   ```markdown
   # ADR-001: Flask Framework Selection
   
   ## Status
   Accepted
   
   ## Context
   We need a web framework for the OnePay payment gateway application. The framework should be:
   - Lightweight and fast
   - Well-documented
   - Extensible with a large ecosystem
   - Suitable for REST APIs
   - Secure by default
   
   ## Decision
   We chose Flask as the web framework for OnePay.
   
   ## Consequences
   **Positive:**
   - Lightweight and minimal overhead
   - Extensive extension ecosystem (Flask-Login, Flask-SQLAlchemy, etc.)
   - Well-documented with large community
   - Easy to deploy with WSGI servers
   - Flexible architecture allows for custom implementations
   
   **Negative:**
   - Requires manual configuration for some features
   - Less opinionated than Django (more decisions to make)
   - Async support requires additional setup
   
   ## References
   - Flask documentation: https://flask.palletsprojects.com/
   ```

4. Create ADR-002: PostgreSQL for Production
   ```markdown
   # ADR-002: PostgreSQL for Production Database
   
   ## Status
   Accepted
   
   ## Context
   We need a production-grade database for OnePay. Requirements include:
   - ACID compliance for transaction integrity
   - Support for complex queries and joins
   - JSON support for flexible data storage
   - Strong replication and backup support
   - Excellent performance for read-heavy workloads
   
   ## Decision
   We selected PostgreSQL as the production database, with SQLite for development/testing.
   
   ## Consequences
   **Positive:**
   - ACID compliance ensures data integrity
   - Excellent JSON support for flexible schemas
   - Strong replication and failover support
   - Mature backup and recovery tools
   - Advanced indexing options
   
   **Negative:**
   - Additional operational complexity vs SQLite
   - Requires separate database server
   - Higher resource requirements
   
   ## References
   - PostgreSQL documentation: https://www.postgresql.org/docs/
   ```

5. Create ADR-003: Redis for Caching
   ```markdown
   # ADR-003: Redis for Caching Layer
   
   ## Status
   Accepted
   
   ## Context
   We need a caching layer to improve performance and reduce database load. Requirements:
   - Fast read/write operations
   - Support for multiple data types
   - TTL (time-to-live) support
   - Persistence options
   - Clustering support for high availability
   
   ## Decision
   We chose Redis as the caching layer with in-memory fallback.
   
   ## Consequences
   **Positive:**
   - Extremely fast (in-memory)
   - Rich data types (strings, lists, sets, hashes)
   - Built-in TTL support
   - Clustering for high availability
   - Mature client libraries
   
   **Negative:**
   - Additional infrastructure component
   - Memory-intensive
   - Requires monitoring for memory usage
   
   ## References
   - Redis documentation: https://redis.io/docs/
   ```

6. Create ADR-004: KoraPay Integration
   ```markdown
   # ADR-004: KoraPay Payment Gateway Integration
   
   ## Status
   Accepted
   
   ## Context
   OnePay needs a payment gateway for processing payments in Nigeria. Requirements:
   - Support for Nigerian Naira (NGN)
   - Virtual account generation
   - Webhook notifications
   - Reliable API uptime
   - Competitive transaction fees
   
   ## Decision
   We integrated KoraPay as the primary payment gateway.
   
   ## Consequences
   **Positive:**
   - Strong presence in Nigerian market
   - Virtual account support
   - Webhook notifications
   - Competitive pricing
   - Good API documentation
   
   **Negative:**
   - Single point of failure (only one gateway)
   - Vendor lock-in risk
   - Limited to Nigerian market primarily
   
   ## References
   - KoraPay documentation: https://korapay.com/docs/
   ```

5. Create ADR-005: Security-First Approach
   ```markdown
   # ADR-005: Security-First Architecture
   
   ## Status
   Accepted
   
   ## Context
   As a payment gateway, security is paramount. We need:
   - Strong authentication and authorization
   - Protection against common web vulnerabilities
   - Audit logging for compliance
   - Encryption at rest and in transit
   - Rate limiting and abuse prevention
   
   ## Decision
   We adopted a security-first architecture with defense in depth.
   
   ## Consequences
   **Positive:**
   - Comprehensive security controls
   - Audit trail for compliance
   - Protection against OWASP Top 10
   - Regular security audits
   - Incident response procedures
   
   **Negative:**
   - Additional development overhead
   - Performance impact from security measures
   - Complexity from multiple security layers
   
   ## References
   - OWASP Top 10: https://owasp.org/www-project-top-ten/
   - PCI DSS: https://www.pcisecuritystandards.org/
   ```

### Acceptance Criteria
- [ ] ADR directory created
- [ ] ADR template documented
- [ ] Key architectural decisions recorded
- [ ] Consequences documented for each decision
- [ ] References included

### Checkpoint Test
```bash
# Verify ADR directory exists
ls docs/adr/
# Expected: ADR files present

# Verify ADR template exists
ls docs/adr/TEMPLATE.md
# Expected: Template file exists

# Verify key ADRs created
ls docs/adr/ | grep -E "ADR-00[1-5]"
# Expected: ADR-001 through ADR-005 present
```

---

## DOC-003: Add Troubleshooting Guide

**File:** `docs/TROUBLESHOOTING.md` (new)  
**Estimated Effort:** 4 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Create troubleshooting guide with common issues:

2. Database Connection Issues:
   ```markdown
   ## Database Connection Issues
   
   ### Symptom
   Application fails to start with database connection error.
   
   ### Common Causes
   - PostgreSQL not running
   - Incorrect database URL in configuration
   - Network connectivity issues
   - Insufficient database permissions
   
   ### Troubleshooting Steps
   1. Check PostgreSQL status:
      ```bash
      sudo systemctl status postgresql
      ```
   
   2. Test database connection:
      ```bash
      psql -h localhost -U onepay -d onepay
      ```
   
   3. Verify environment variables:
      ```bash
      echo $DATABASE_URL
      ```
   
   4. Check database logs:
      ```bash
      sudo tail -f /var/log/postgresql/postgresql-*.log
      ```
   
   ### Solution
   - Start PostgreSQL: `sudo systemctl start postgresql`
   - Update DATABASE_URL in .env
   - Grant necessary permissions to database user
   ```

3. Redis Connection Issues:
   ```markdown
   ## Redis Connection Issues
   
   ### Symptom
   Cache operations fail with connection error.
   
   ### Common Causes
   - Redis not running
   - Incorrect Redis URL
   - Redis max memory reached
   - Network connectivity issues
   
   ### Troubleshooting Steps
   1. Check Redis status:
      ```bash
      redis-cli ping
      ```
   
   2. Check Redis logs:
      ```bash
      sudo tail -f /var/log/redis/redis-server.log
      ```
   
   3. Check memory usage:
      ```bash
      redis-cli INFO memory
      ```
   
   ### Solution
   - Start Redis: `sudo systemctl start redis`
   - Update REDIS_URL in .env
   - Configure Redis maxmemory policy
   ```

4. KoraPay API Errors:
   ```markdown
   ## KoraPay API Errors
   
   ### Symptom
   Payment link creation fails with API error.
   
   ### Common Causes
   - Invalid API credentials
   - Insufficient balance
   - API rate limit exceeded
   - Network connectivity issues
   
   ### Troubleshooting Steps
   1. Test API credentials:
      ```bash
      curl -H "Authorization: Bearer $KORAPAY_SECRET_KEY" \
           https://api.korapay.com/merchant/api/v1/balance
      ```
   
   2. Check circuit breaker status:
      ```bash
      # Check logs for circuit breaker events
      grep "circuit_breaker" logs/app.log
      ```
   
   3. Verify API status:
      ```bash
      curl https://status.korapay.com
      ```
   
   ### Solution
   - Verify KORAPAY_SECRET_KEY in .env
   - Check KoraPay dashboard for balance
   - Wait for rate limit to reset
   - Enable circuit breaker auto-recovery
   ```

5. Email Delivery Issues:
   ```markdown
   ## Email Delivery Issues
   
   ### Symptom
   Password reset emails not delivered.
   
   ### Common Causes
   - Incorrect SMTP configuration
   - Email blocked by spam filters
   - SMTP server down
   - Invalid email address
   
   ### Troubleshooting Steps
   1. Test SMTP connection:
      ```bash
      python -c "
      import smtplib
      server = smtplib.SMTP('smtp.example.com', 587)
      server.starttls()
      server.login('user@example.com', 'password')
      server.quit()
      "
      ```
   
   2. Check email logs:
      ```bash
      tail -f logs/email.log
      ```
   
   3. Verify email in spam folder
   
   ### Solution
   - Update SMTP settings in .env
   - Configure SPF/DKIM/DMARC records
   - Use transactional email service (SendGrid)
   - Verify recipient email address
   ```

6. Session Issues:
   ```markdown
   ## Session Issues
   
   ### Symptom
   Users logged out unexpectedly or session not persisting.
   
   ### Common Causes
   - Redis session storage not configured
   - Session timeout too short
   - Cookie settings incorrect
   - Multiple application instances without shared session storage
   
   ### Troubleshooting Steps
   1. Check session configuration:
      ```bash
      echo $SESSION_TYPE
      echo $SESSION_REDIS
      ```
   
   2. Verify Redis session storage:
      ```bash
      redis-cli KEYS "onepay:session:*"
      ```
   
   3. Check browser console for cookie errors
   
   ### Solution
   - Configure Flask-Session with Redis
   - Increase SESSION_PERMANENT lifetime
   - Verify cookie settings (secure, httponly, samesite)
   - Ensure all instances use same Redis for sessions
   ```

7. Webhook Delivery Failures:
   ```markdown
   ## Webhook Delivery Failures
   
   ### Symptom
   Webhooks not delivered to merchant URLs.
   
   ### Common Causes
   - Merchant URL unreachable
   - URL blocked by webhook blacklist (SSRF)
   - Signature verification failed
   - Retry limit exceeded
   
   ### Troubleshooting Steps
   1. Check webhook blacklist:
      ```python
      from database import get_db
      from models.webhook_blacklist import WebhookBlacklist
       with get_db() as db:
           blacklisted = db.query(WebhookBlacklist).all()
           print(blacklisted)
      ```
   
   2. Check webhook delivery logs:
      ```bash
      grep "webhook" logs/app.log
      ```
   
   3. Test webhook URL manually:
      ```bash
      curl -X POST https://merchant.example.com/webhook \
           -H "Content-Type: application/json" \
           -d '{"test": "data"}'
      ```
   
   ### Solution
   - Verify merchant URL is accessible and public
   - Check if URL was blacklisted (SSRF protection)
   - Verify signature verification logic
   - Increase retry limit or fix merchant endpoint
   ```

8. Escalation Path:
   ```markdown
   ## Escalation Path
   
   If issues cannot be resolved using this guide:
   
   1. Check existing GitHub issues for similar problems
   2. Create a new issue with:
      - Detailed description of the problem
      - Steps to reproduce
      - Relevant logs and error messages
      - Environment details (OS, Python version, etc.)
   3. For urgent production issues:
      - Contact: support@yourdomain.com
      - Emergency: +1-XXX-XXX-XXXX
   ```

### Acceptance Criteria
- [ ] Common issues documented
- [ ] Troubleshooting steps clear and actionable
- [ ] Solutions verified
- [ ] Escalation path defined
- [ ] Logs and commands included

### Checkpoint Test
```bash
# Verify troubleshooting guide exists
ls docs/TROUBLESHOOTING.md
# Expected: File exists

# Verify key sections present
grep -q "Database Connection" docs/TROUBLESHOOTING.md
grep -q "Redis Connection" docs/TROUBLESHOOTING.md
grep -q "KoraPay API" docs/TROUBLESHOOTING.md
grep -q "Email Delivery" docs/TROUBLESHOOTING.md
grep -q "Session Issues" docs/TROUBLESHOOTING.md
grep -q "Webhook Delivery" docs/TROUBLESHOOTING.md
```

---

## Phase 6 Checkpoint Test

```bash
#!/bin/bash
# Phase 6 Documentation Checkpoint Test

echo "=== Phase 6 Documentation Checkpoint ==="
echo ""

echo "1. Testing API Examples Documentation..."
ls docs/API_EXAMPLES.md && echo "✓ API examples file exists" || echo "✗ API examples file missing"
grep -q "Python" docs/API_EXAMPLES.md && echo "✓ Python examples present" || echo "✗ Python examples missing"
grep -q "JavaScript" docs/API_EXAMPLES.md && echo "✓ JavaScript examples present" || echo "✗ JavaScript examples missing"
grep -q "PHP" docs/API_EXAMPLES.md && echo "✓ PHP examples present" || echo "✗ PHP examples missing"
grep -q "cURL" docs/API_EXAMPLES.md && echo "✓ cURL examples present" || echo "✗ cURL examples missing"

echo "2. Testing Architecture Decision Records..."
ls docs/adr/ && echo "✓ ADR directory exists" || echo "✗ ADR directory missing"
ls docs/adr/TEMPLATE.md && echo "✓ ADR template exists" || echo "⚠ ADR template missing"
ls docs/adr/ | grep -E "ADR-00[1-5]" | wc -l | grep -q "[1-5]" && echo "✓ Key ADRs present" || echo "✗ Key ADRs missing"

echo "3. Testing Troubleshooting Guide..."
ls docs/TROUBLESHOOTING.md && echo "✓ Troubleshooting guide exists" || echo "✗ Troubleshooting guide missing"
grep -q "Database Connection" docs/TROUBLESHOOTING.md && echo "✓ Database section present" || echo "✗ Database section missing"
grep -q "Redis Connection" docs/TROUBLESHOOTING.md && echo "✓ Redis section present" || echo "✗ Redis section missing"
grep -q "Escalation" docs/TROUBLESHOOTING.md && echo "✓ Escalation path present" || echo "✗ Escalation path missing"

echo ""
echo "=== Phase 6 Checkpoint Complete ==="
```

---

## Phase 6 Summary

**Total Tasks:** 3  
**Total Estimated Effort:** ~18 hours  
**Risk Profile:** 3 Low  
**Dependencies:** None

**Completion Criteria:**
- All 3 checkpoint tests pass
- API examples in multiple languages
- Architecture decision records created
- Troubleshooting guide comprehensive

---

## Overall Implementation Plan Summary

**Total Phases:** 6  
**Total Tasks:** 31  
**Total Estimated Effort:** ~289 hours

### Phase Breakdown
- Phase 1 (Security): 9 tasks, ~50 hours
- Phase 2 (Performance): 6 tasks, ~43 hours
- Phase 3 (Features): 6 tasks, ~78 hours
- Phase 4 (Testing): 6 tasks, ~70 hours
- Phase 5 (Operations): 5 tasks, ~30 hours
- Phase 6 (Documentation): 3 tasks, ~18 hours

### Risk Profile
- High Risk: 4 tasks (PERF-004, FEAT-003, FEAT-005, FEAT-006)
- Medium Risk: 12 tasks
- Low Risk: 15 tasks

### Dependencies
- Internal dependencies: 3 (SEC-007→PERF-004, FEAT-006→FEAT-005, OPS-003→OPS-002)

### Recommended Execution Order
1. **Sprint 1 (2 weeks):** Phase 1 Critical Security (SEC-001 through SEC-006)
2. **Sprint 2 (2 weeks):** Phase 1 remaining (SEC-007, SEC-008, SEC-009) + Phase 2 quick wins (PERF-002, PERF-003)
3. **Sprint 3 (3 weeks):** Phase 2 remaining (PERF-001, PERF-004, PERF-005, PERF-006)
4. **Sprint 4 (4 weeks):** Phase 3 Features (FEAT-001, FEAT-002, FEAT-004)
5. **Sprint 5 (4 weeks):** Phase 3 remaining (FEAT-003, FEAT-005, FEAT-006)
6. **Sprint 6 (4 weeks):** Phase 4 Testing (TEST-001, TEST-002, TEST-004)
7. **Sprint 7 (3 weeks):** Phase 4 remaining (TEST-003, TEST-005, TEST-006)
8. **Sprint 8 (2 weeks):** Phase 5 Operations (OPS-001, OPS-002, OPS-003)
9. **Sprint 9 (1 week):** Phase 5 remaining (OPS-004, OPS-005) + Phase 6 Documentation (DOC-001, DOC-002, DOC-003)

**Total Timeline:** ~25 weeks (~6 months)

### Success Criteria
- All 31 tasks completed
- All 6 phase checkpoint tests pass
- Security posture improved (16/18 → 18/18 vulnerabilities resolved)
- Test coverage >= 90%
- Performance metrics improved (60%+ query reduction, 40%+ query time reduction)
- New features operational (refunds, analytics, multi-currency, etc.)
- Monitoring and alerting functional
- Documentation comprehensive and up-to-date

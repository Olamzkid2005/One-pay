# Security Audit Skill

Perform comprehensive security audit of the OnePay codebase.

## When to Use
- Before production deployment
- After adding new authentication code
- User mentions "security audit" or "vulnerability"
- Quarterly security review

## How to Use
1. Scan for common vulnerabilities:
   - SQL injection in raw SQL queries
   - XSS in template rendering
   - CSRF on state-changing endpoints
   - Hardcoded secrets in code
   - Weak cryptography or password hashing

2. Check these critical files:
   - `blueprints/auth.py` - authentication logic
   - `services/korapay.py` - payment security
   - `blueprints/webhooks.py` - webhook signature verification
   - `services/webhook.py` - outbound webhook HMAC
   - `config.py` - secret key configuration

3. Run security tests:
   ```bash
   pytest tests/unit/test_webhook_signature.py -v
   pytest tests/test_csrf_bypass.py -v
   ```

4. Verify security headers (run health check):
   - CSP, HSTS, X-Frame-Options
   - Content-Type options
   - Rate limiting active

## Report Format
```
## Critical (must fix)
- [Issue] ... in file:line
## High (fix soon)
- [Issue] ...
## Medium (consider)
- [Issue] ...
```

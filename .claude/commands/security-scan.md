# Security Scan

Run a security vulnerability scan on the codebase. Use the security-vulnerability-scanner agent to check for:

1. **OWASP Top 10** vulnerabilities (injection, broken auth, sensitive data exposure, etc.)
2. **Secrets in code** (API keys, passwords, tokens hardcoded)
3. **Dependency vulnerabilities** (outdated packages with known CVEs)
4. **Flask-specific issues** (missing security headers, CSRF protection, etc.)

Check these files specifically:
- `services/korapay.py` - payment integration
- `blueprints/auth.py` - authentication
- `services/webhook.py` - webhook handling
- `config.py` - configuration security

Report vulnerabilities by severity and provide remediation suggestions.

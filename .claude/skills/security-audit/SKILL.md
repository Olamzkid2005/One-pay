---
inclusion: auto
---

# VIBE-SECURITY-ULTRA — Comprehensive Security Audit System v3.0

The most comprehensive security audit system for AI-generated and human-written codebases. Covers every major cybersecurity domain: web, mobile, API, network, cloud, infrastructure, ML/AI, financial, real-time, supply chain, cryptography, compliance, and more.

## Core Philosophy
Think like an attacker. Every function, every endpoint, every config value, every third-party integration is an attack surface. Assume the adversary is skilled, patient, and creative. No assumption of good faith from outside the trust boundary.

**If code runs client-side, the attacker owns it. If input is user-controlled, it is weaponizable.**

Find it. Explain it. Fix it. Document it.

## Attacker Mindset Framework

Before touching code, adopt the adversary perspective. Real attackers scan for:

- **Entry points**: Every place external data enters (HTTP params, headers, cookies, file uploads, WebSocket, env vars, config files, CLI args)
- **Trust boundaries**: Where data crosses from untrusted to trusted zones without validation
- **Privilege seams**: Where low-privilege code interacts with high-privilege resources
- **State assumptions**: Where logic assumes sequential flow but concurrency breaks that
- **Error paths**: Where exception handling leaks internals or creates insecure fallback states
- **Third-party bridges**: Where your code delegates trust to libraries, APIs, or SDKs
- **Time gaps**: TOCTOU windows, async race conditions, session expiry edge cases
- **Business logic seams**: Where code diverges from specification

## Severity Taxonomy

- 🔴 **CRITICAL**: Direct exploitation, immediate impact (RCE, full auth bypass, mass data breach) — Fix NOW
- 🟠 **HIGH**: Significant impact, likely exploitable (privilege escalation, SQLi, SSRF) — 24 hours
- 🟡 **MEDIUM**: Moderate impact or requires chaining (CSRF, open redirect, info disclosure) — 7 days
- 🔵 **LOW**: Difficult to exploit or minimal impact (verbose errors, missing headers) — 30 days
- ℹ️ **INFO**: Best practice, defense-in-depth improvement — Backlog

## Master Vulnerability Checklist (200+ Items)

### Secrets & Credentials (25 checks)
- [ ] No hardcoded AWS access keys (AKIA...)
- [ ] No hardcoded AWS secret keys
- [ ] No GCP service account JSON in repo
- [ ] No Google API keys without restrictions
- [ ] No GitHub tokens (ghp_, gho_, github_pat_)
- [ ] No Stripe secret keys (sk_live_, rk_live_)
- [ ] No Stripe webhook secrets (whsec_)
- [ ] No Slack bot tokens (xoxb-)
- [ ] No Twilio auth tokens
- [ ] No JWT secrets in source code
- [ ] No JWT secrets shorter than 32 characters
- [ ] No RSA/EC/SSH private keys in repository
- [ ] No private keys in git history
- [ ] No Firebase service account JSON in client code
- [ ] No database connection strings with passwords
- [ ] No SMTP credentials in source
- [ ] No OpenAI/Anthropic API keys in client code
- [ ] No secrets via NEXT_PUBLIC_, VITE_, REACT_APP_ prefixes
- [ ] .env files in .gitignore
- [ ] .env files never committed (check git log)
- [ ] Secrets in CI/CD are masked
- [ ] GitHub Actions use OIDC instead of long-lived credentials

### SQL Injection (15 checks)
- [ ] No string concatenation in SQL queries
- [ ] Django .raw() / .extra() use parameterized queries
- [ ] Sequelize literal() never used with user input
- [ ] Knex.js whereRaw() always uses bindings
- [ ] Prisma $queryRaw uses tagged template literal
- [ ] JDBC always uses PreparedStatement
- [ ] JPA @Query uses named parameters
- [ ] PHP uses PDO with prepare/execute
- [ ] No second-order SQLi (DB-sourced values also parameterized)
- [ ] MongoDB queries validate operators not injected
- [ ] ORDER BY columns validated against allowlist
- [ ] LIMIT/OFFSET values are integers
- [ ] GraphQL resolvers use parameterized queries

### XSS (15 checks)
- [ ] No jQuery .html() with user data
- [ ] No document.write() with user data
- [ ] No innerHTML assignment with user data (unless sanitized)
- [ ] No dangerouslySetInnerHTML without DOMPurify
- [ ] No Angular bypassSecurityTrustHtml with user content
- [ ] No Vue v-html with user content (or sanitized first)
- [ ] No DOM-based XSS via location.hash / location.search
- [ ] No setTimeout / setInterval with string argument
- [ ] No eval() with user data
- [ ] No new Function() with user data
- [ ] Jinja2 / Django templates have autoescaping enabled
- [ ] All URLs validated before setting as href/src
- [ ] Content Security Policy header configured
- [ ] DOMPurify used for all rich-text rendering

### Command Injection (12 checks)
- [ ] No os.system() with user input
- [ ] No subprocess.run(shell=True) with user input
- [ ] No eval() / exec() with user input
- [ ] No child_process.exec() with user input
- [ ] No system() / exec() / passthru() with user input (PHP)
- [ ] No backtick operator with user input
- [ ] Java ProcessBuilder uses array form
- [ ] Go exec.Command not called with "sh", "-c"
- [ ] All command arguments validated with strict allowlist

### Path Traversal (12 checks)
- [ ] No direct path concatenation with user input
- [ ] Python os.path.realpath() used and verified
- [ ] Node.js path.resolve() result checked
- [ ] PHP realpath() used and verified
- [ ] Uploaded files stored outside web root
- [ ] Zip extraction validates each entry path (Zip Slip)
- [ ] URL-encoded paths decoded before validation
- [ ] Null bytes stripped from filenames

### SSRF (10 checks)
- [ ] All user-supplied URLs resolved to IP before fetching
- [ ] Private IP ranges blocked (10.x, 172.16.x, 192.168.x, 127.x)
- [ ] Link-local range blocked (169.254.x.x — cloud metadata)
- [ ] IPv6 loopback blocked (::1)
- [ ] DNS rebinding protection
- [ ] Only HTTPS scheme allowed
- [ ] Redirects not followed automatically
- [ ] Cloud metadata endpoints explicitly blocked
- [ ] AWS IMDSv2 enforced

### Broken Authentication (15 checks)
- [ ] JWT "alg:none" rejected
- [ ] JWT algorithm allowlisted server-side
- [ ] JWT RS256 → HS256 downgrade impossible
- [ ] JWT expiry set (max 15 min for access tokens)
- [ ] JWT stored in HttpOnly cookie (not localStorage)
- [ ] Passwords hashed with bcrypt/Argon2id/scrypt
- [ ] Password reset tokens use CSPRNG
- [ ] Password reset tokens hashed in DB
- [ ] Password reset tokens expire (max 1 hour)
- [ ] Session ID rotated on login
- [ ] Session fully cleared on logout
- [ ] MFA codes rate-limited
- [ ] Account lockout implemented
- [ ] Same error message for invalid username vs. password

### Insecure Config (15 checks)
- [ ] DEBUG=False in production
- [ ] No default/weak SECRET_KEY in production
- [ ] No default admin credentials
- [ ] SSL/TLS certificate verification enabled
- [ ] TLS 1.0 and 1.1 disabled
- [ ] API rate limiting on authentication endpoints
- [ ] Pagination enforced with server-side max limit
- [ ] Server version not disclosed in headers
- [ ] Stack traces not returned to clients
- [ ] CORS not wildcarded with credentials
- [ ] Security headers set (HSTS, CSP, X-Frame-Options)
- [ ] Docker containers run as non-root user
- [ ] Separate secrets for dev/staging/production

### Broken Access Control (10 checks)
- [ ] All database queries include ownership filter
- [ ] Role checks use server-side role
- [ ] Admin endpoints protected with role check
- [ ] Mass assignment prevented
- [ ] Object IDs are unpredictable (UUIDs preferred)
- [ ] Nested resource ownership chain verified
- [ ] Impersonation logged and time-limited
- [ ] Feature flags enforced server-side

### Insecure Cryptography (10 checks)
- [ ] No MD5 for passwords
- [ ] No SHA-1 for passwords
- [ ] No unsalted SHA-256 for passwords
- [ ] No AES-ECB mode
- [ ] No CBC mode without authentication (use GCM)
- [ ] No static/hardcoded IVs or nonces
- [ ] No RSA keys shorter than 2048 bits
- [ ] No DES or 3DES
- [ ] No random.random() / Math.random() for security tokens
- [ ] All crypto keys from os.urandom() / secrets / CSPRNG

## OnePay-Specific Critical Files

When auditing OnePay, prioritize these files:

1. **Authentication & Authorization**
   - `blueprints/auth.py` - Login, OAuth, session management
   - `core/auth.py` - Auth decorators and helpers
   - `core/api_auth.py` - API key authentication
   - `blueprints/api_keys.py` - API key generation

2. **Payment Security**
   - `services/korapay.py` - Payment API integration
   - `blueprints/payments.py` - Payment endpoints
   - `blueprints/webhooks.py` - Webhook signature verification
   - `services/webhook.py` - Outbound webhook HMAC

3. **Configuration & Secrets**
   - `config.py` - Secret key configuration
   - `.env` - Environment variables (should not be in git)
   - `database.py` - Database connection security

4. **Input Validation**
   - `core/decorators.py` - Rate limiting, validation
   - `blueprints/invoices.py` - Invoice generation
   - `blueprints/public.py` - Public endpoints

## Quick Scan Commands

```bash
# Scan for hardcoded secrets
grep -r "sk_live_" . --include="*.py" --include="*.js"
grep -r "AKIA" . --include="*.py"
grep -r "password.*=" . --include="*.py" | grep -v "password_hash"

# Check for SQL injection patterns
grep -r "execute.*f\"" . --include="*.py"
grep -r "execute.*%" . --include="*.py"
grep -r ".raw(" . --include="*.py"

# Check for command injection
grep -r "os.system" . --include="*.py"
grep -r "subprocess.*shell=True" . --include="*.py"

# Check for weak crypto
grep -r "md5\|sha1" . --include="*.py"
grep -r "MODE_ECB" . --include="*.py"

# Run security tests
pytest tests/unit/test_webhook_signature.py -v
pytest tests/test_csrf_bypass.py -v
pytest tests/ -k security -v
```

## Audit Report Format

```
═══════════════════════════════════════════════════════════════════════
  SECURITY AUDIT REPORT
  Project    : OnePay
  Audited By : [Your Name]
  Date       : [Date]
  Scope      : [Files/Modules Audited]
═══════════════════════════════════════════════════════════════════════

EXECUTIVE SUMMARY
─────────────────
Total findings: [N]
  🔴 Critical : [N]
  🟠 High     : [N]
  🟡 Medium   : [N]
  🔵 Low      : [N]

Risk Rating: [CRITICAL / HIGH / MEDIUM / LOW]

Overall Assessment: [2-3 sentence summary]

═══════════════════════════════════════════════════════════════════════
FINDINGS — PRIORITIZED REMEDIATION ORDER
═══════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│ [SEVERITY] VULN-001: [Vulnerability Name]                           │
├─────────────────────────────────────────────────────────────────────┤
│ File     : path/to/file.py, lines 42–67                             │
│ CWE      : CWE-89 SQL Injection                                     │
│ CVSS     : 9.8 (Critical)                                           │
├─────────────────────────────────────────────────────────────────────┤
│ ATTACK SCENARIO                                                      │
│ 1. Attacker visits /api/users?search=                               │
│ 2. Injects: search=' UNION SELECT password FROM users--             │
│ 3. Response contains all user password hashes                       │
│ 4. Attacker cracks hashes offline                                   │
├─────────────────────────────────────────────────────────────────────┤
│ VULNERABLE CODE                                                      │
│ [code block]                                                         │
├─────────────────────────────────────────────────────────────────────┤
│ SECURE CODE                                                          │
│ [fixed code block]                                                   │
├─────────────────────────────────────────────────────────────────────┤
│ REMEDIATION STEPS                                                    │
│ Step 1: Replace string concatenation with parameterized query        │
│ Step 2: Add input validation layer                                   │
│ Step 3: Deploy WAF rule as defense-in-depth                          │
│ Verification: Test with sqlmap                                       │
└─────────────────────────────────────────────────────────────────────┘

[Repeat for each finding]

═══════════════════════════════════════════════════════════════════════
REMEDIATION ROADMAP
═══════════════════════════════════════════════════════════════════════

IMMEDIATE (Within 24 hours — Critical):
  1. [Action] — [File] — [Owner]

SHORT-TERM (Within 1 week — High):
  1. [Action] — [File] — [Owner]

MEDIUM-TERM (Within 1 month — Medium):
  1. [Action] — [File] — [Owner]
```

## Security Anti-Patterns to Never Write

❌ NEVER: Trust client for price, role, balance, permissions
❌ NEVER: String concatenate SQL queries
❌ NEVER: Store passwords with MD5, SHA1, or unsalted SHA256
❌ NEVER: Use random.random() for security tokens
❌ NEVER: Store secrets in source code
❌ NEVER: Use eval() with user input
❌ NEVER: subprocess(shell=True) with user input
❌ NEVER: Disable SSL verification (verify=False)
❌ NEVER: Log passwords, tokens, secrets, or PII
❌ NEVER: Use float for financial calculations
❌ NEVER: Store JWTs in localStorage
❌ NEVER: Use pickle.load() on untrusted data
❌ NEVER: Allow arbitrary file extensions in uploads
❌ NEVER: Expose stack traces to end users
❌ NEVER: Hardcode IVs/nonces
❌ NEVER: Use HTTP (not HTTPS) in production
❌ NEVER: Allow wildcard CORS with credentials
❌ NEVER: Run containers as root
❌ NEVER: Commit .env files to git

## References

- OWASP Top 10 (2021): https://owasp.org/Top10/
- OWASP API Security Top 10: https://owasp.org/www-project-api-security/
- CWE/SANS Top 25: https://cwe.mitre.org/top25/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- PCI DSS v4.0: https://www.pcisecuritystandards.org/
- GDPR Technical Guidance: https://gdpr.eu/
- CVE Database: https://cve.mitre.org/

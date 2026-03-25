# Security Upgrade Guide

## Quick Start

Follow these steps to apply the latest security fixes:

### 1. Install New Dependencies

```bash
pip install -r requirements.txt
```

This installs bcrypt 4.1.2 for enhanced password hashing.

### 2. Run Database Migration

```bash
alembic upgrade head
```

This creates the migration record (no schema changes needed).

### 3. Restart Your Application

**Development:**
```bash
python app.py
```

**Production (gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app --access-logfile - --error-logfile -
```

**Docker:**
```bash
docker-compose down
docker-compose up --build -d
```

---

## What Changed?

### ✅ Password Hashing (bcrypt)
- New users get bcrypt hashes automatically
- Existing users migrate on next login (seamless)
- No action required from users

### ✅ Content-Type Validation
- API endpoints now require `Content-Type: application/json`
- Frontend already sends correct headers
- No changes needed to your code

### ✅ Session Security
- Changed from `SameSite=Lax` to `SameSite=Strict`
- Stronger CSRF protection
- No impact on normal usage

### ✅ Security Headers
- Added 3 additional headers for defense-in-depth
- Improves security score
- No visible changes to users

---

## Testing

### Quick Health Check

```bash
# Check application is running
curl http://localhost:5000/health

# Verify security headers
curl -I http://localhost:5000/ | grep -E "(X-XSS|X-Download|SameSite)"
```

### Test Password Hashing

```bash
# Register a new user (will use bcrypt)
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser123&email=test@example.com&password=SecurePass123!&password2=SecurePass123!&csrf_token=YOUR_TOKEN"

# Login with existing user (will migrate to bcrypt)
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=youruser&password=yourpass&csrf_token=YOUR_TOKEN"
```

### Test Content-Type Validation

```bash
# This should fail (no Content-Type)
curl -X POST http://localhost:5000/api/payments/link \
  -H "Cookie: session=YOUR_SESSION" \
  -d '{"amount": 1000}'

# This should work (correct Content-Type)
curl -X POST http://localhost:5000/api/payments/link \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION" \
  -H "X-CSRFToken: YOUR_TOKEN" \
  -d '{"amount": 1000, "currency": "NGN"}'
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'bcrypt'"

**Solution:**
```bash
pip install bcrypt==4.1.2
```

### Issue: "415 Unsupported Media Type" on API calls

**Solution:** Ensure your API client sends `Content-Type: application/json` header.

**JavaScript example:**
```javascript
fetch('/api/payments/link', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({ amount: 1000 })
})
```

### Issue: Existing users can't log in

**Solution:** This shouldn't happen (werkzeug fallback is in place), but if it does:

1. Check logs for errors
2. Verify bcrypt is installed: `pip show bcrypt`
3. Test with a new user account
4. Contact support if issue persists

### Issue: Session not persisting after login

**Solution:** This is expected if you're testing cross-site requests. `SameSite=Strict` only allows same-site cookies.

---

## Rollback (If Needed)

If you encounter issues, you can rollback:

### Rollback Code Changes
```bash
git checkout HEAD~1 models/user.py blueprints/payments.py blueprints/auth.py app.py requirements.txt
pip install -r requirements.txt
```

### Rollback Database Migration
```bash
alembic downgrade -1
```

### Restart Application
```bash
# Development
python app.py

# Production
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Backup database
- [ ] Test in staging environment first
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run migration: `alembic upgrade head`
- [ ] Test login with existing user
- [ ] Test registration with new user
- [ ] Verify API endpoints work
- [ ] Check security headers: `curl -I https://yourdomain.com`
- [ ] Monitor logs for errors
- [ ] Have rollback plan ready

---

## Performance Impact

All changes have minimal performance impact:

- **bcrypt**: ~100ms per password hash (intentionally slow for security)
- **Content-Type validation**: <1ms per request
- **SameSite=Strict**: No performance impact
- **Security headers**: <1ms per response

---

## Questions?

- Review: `SECURITY_FIXES_APPLIED_3.md` for detailed changes
- Check: `SECURITY.md` for complete security documentation
- Contact: security@yourdomain.com

---

**Last Updated**: 2026-03-24  
**Version**: 3.0  
**Status**: ✅ Ready for Production

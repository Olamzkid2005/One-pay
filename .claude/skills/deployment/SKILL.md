---
inclusion: auto
---

# Deployment Skill

Deploy OnePay to production or staging environment.

## When to Use
- User wants to deploy the application
- User mentions "deploy" or "release"
- Preparing for production launch

## Pre-Deployment Checklist
1. Run tests: `pytest tests/ -v`
2. Run migrations: `alembic upgrade head`
3. Check environment: `APP_ENV=production` in .env
4. Verify secrets set:
   - `SECRET_KEY` (generate with `python generate_secrets.py`)
   - `KORAPAY_SECRET_KEY` (real key for production)
   - `HMAC_SECRET` (generate with `python generate_secrets.py`)
5. Enable HTTPS: `ENFORCE_HTTPS=true`

## Deployment Methods

### Docker
```bash
docker-compose up --build -d
```

### Direct (Gunicorn)
```bash
gunicorn app:app --workers 4 --timeout 60 --bind 0.0.0.0:5000
```

### Health Verification
```bash
curl https://your-domain.com/health
```

## Post-Deployment
1. Check Prometheus metrics at `/metrics`
2. Verify rate limiting active
3. Test payment flow in sandbox mode first
4. Monitor error logs for first 24 hours

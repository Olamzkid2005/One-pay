---
inclusion: auto
---

# Rate Limiting Skill

Understand and debug rate limiting in OnePay.

## When to Use
- User reports being rate limited unexpectedly
- Testing rate limit behavior
- Adjusting rate limits

## Rate Limit Configuration
Set via environment variables:
- `RATE_LIMIT_LINK_CREATE` - Payment link creation
- `RATE_LIMIT_VERIFY` - Verification checks
- `RATE_LIMIT_API_LINK_CREATE` - API link creation
- `RATE_LIMIT_API_STATUS_CHECK` - API status checks
- `RATE_LIMIT_VERIFY_PAGE_ATTEMPTS` - Verify page attempts per window

## How Rate Limiting Works
1. Request hits rate limiter service
2. Check current count in rate_limit table
3. If under limit, increment and allow
4. If over limit, return 429 Too Many Requests

## Test Rate Limiting
```bash
# Run rate limit tests
pytest tests/test_api_rate_limits.py -v

# Test with curl (fills up limit)
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/api/v1/verify/test
done
```

## Key Files
- `services/rate_limiter.py` - Rate limiting logic
- `models/rate_limit.py` - Rate limit tracking model
- `blueprints/public.py` - Verify endpoint with rate limits

## Response Headers
- `X-RateLimit-Limit` - Maximum requests allowed
- `X-RateLimit-Remaining` - Requests remaining
- `Retry-After` - Seconds to wait (when limited)

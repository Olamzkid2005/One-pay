# KoraPay Setup Guide

This guide provides instructions for setting up KoraPay as the payment provider for OnePay.

## Prerequisites

- KoraPay merchant account
- Admin access to OnePay configuration
- Access to production environment variables

## Step 1: Obtain KoraPay Credentials

### From KoraPay Dashboard

1. Log in to [KoraPay Dashboard](https://dashboard.korapay.com)
2. Navigate to Settings → API Keys
3. Generate a new API key (or use existing)
4. Note the following:
   - `KORAPAY_SECRET_KEY` - Your secret API key
   - `KORAPAY_PUBLISHABLE_KEY` - Your publishable key (optional)

### Webhook Configuration

1. In KoraPay Dashboard, go to Settings → Webhooks
2. Add webhook URL: `https://api.onepay.ng/api/webhooks/korapay`
3. Generate webhook secret
4. Note the `KORAPAY_WEBHOOK_SECRET`

### Test Mode vs Production

| Environment | URL | Key Prefix |
|-------------|-----|------------|
| Sandbox | https://api.korapay.com/merchant/api/v1 | sk_test_ |
| Production | https://api.korapay.com/merchant/api/v1 | sk_live_ |

## Step 2: Configure Environment Variables

### Development (.env)

```bash
# KoraPay Configuration
KORAPAY_SECRET_KEY=sk_test_your_test_key_here
KORAPAY_WEBHOOK_SECRET=your_webhook_secret_here
KORAPAY_BASE_URL=https://api.korapay.com/merchant/api/v1
KORAPAY_USE_SANDBOX=true
KORAPAY_TIMEOUT_SECONDS=30
KORAPAY_CONNECT_TIMEOUT=10
KORAPAY_MAX_RETRIES=3

# Feature Flag
KORAPAY_ENABLED=true
```

### Production (.env.production)

```bash
# KoraPay Configuration (Production)
KORAPAY_SECRET_KEY=sk_live_your_production_key_here
KORAPAY_WEBHOOK_SECRET=your_production_webhook_secret_here
KORAPAY_BASE_URL=https://api.korapay.com/merchant/api/v1
KORAPAY_USE_SANDBOX=false
KORAPAY_TIMEOUT_SECONDS=30
KORAPAY_CONNECT_TIMEOUT=10
KORAPAY_MAX_RETRIES=3

# Feature Flag
KORAPAY_ENABLED=true
```

### Security Requirements

| Variable | Minimum Length | Pattern |
|----------|---------------|---------|
| KORAPAY_SECRET_KEY | 32 characters | sk_live_* |
| KORAPAY_WEBHOOK_SECRET | 32 characters | Any |

## Step 3: Verify Configuration

### Test Configuration Validation

```bash
# Validate production configuration
python -c "
from services.korapay import KoraPayService
kp = KoraPayService()
print('Configured:', kp.is_configured())
print('Mode:', 'Production' if not kp._is_mock() else 'Mock')
"

# Expected output:
# Configured: True
# Mode: Production
```

### Test API Connectivity

```bash
# Run integration tests
python -m pytest tests/integration/test_korapay_flow.py -v

# Run with specific test
python -m pytest tests/integration/test_korapay_flow.py::TestCompleteFlow::test_create_and_confirm_payment_live_mode -v -s
```

## Step 4: Configure Webhooks

### KoraPay Dashboard Webhook Settings

1. URL: `https://api.onepay.ng/api/webhooks/korapay`
2. Events to subscribe:
   - `charge.succeeded`
   - `charge.failed`
   - `charge.pending`

### Verify Webhook Signature

```bash
# Test webhook endpoint
curl -X POST https://api.onepay.ng/api/webhooks/korapay \
  -H "Content-Type: application/json" \
  -H "x-korapay-signature: test_signature" \
  -d '{"event": "test", "data": {}}'
```

## Step 5: Monitoring Setup

### Prometheus Metrics

Ensure `prometheus_client` is installed:

```bash
pip install prometheus_client>=0.17.0
```

Metrics exposed at `/metrics`:
- `korapay_requests_total` - Total KoraPay API requests
- `korapay_request_duration_seconds` - Request latency histogram
- `korapay_errors_total` - Total errors by type

### Grafana Dashboard

Import dashboard from `grafana/dashboards/korapay-integration.json`

Key panels:
- Request Rate
- Error Rate
- Latency Percentiles (p50, p95, p99)
- Success Rate Gauge
- Circuit Breaker State

### Alert Configuration

Prometheus alerts defined in `prometheus/alerts/korapay.yml`:
- `KoraPayAPIErrorRateHigh` - Error rate > 5%
- `KoraPayAPILatencyHigh` - p95 latency > 5s
- `CircuitBreakerOpen` - Circuit breaker in OPEN state

## Step 6: Bank Account Setup

### Supported Banks

KoraPay supports the following Nigerian banks for virtual accounts:

| Bank Code | Bank Name |
|-----------|-----------|
| 057 | Zenith Bank |
| 058 | Guaranty Trust Bank (GTBank) |
| 044 | Access Bank |
| 023 | Sterling Bank |
| 215 | Unity Bank |
| 035 | Wema Bank |
| 232 | Sterling Bank |
| 301 | Stanbic IBTC |
| 071 | Access Bank (Diamond) |
| 082 | Keystone Bank |
| 221 | First Bank of Nigeria |
| 211 | Unity Bank |

### Virtual Account Features

- NUBAN compliant (10-digit account numbers)
- Instant generation
- 30-minute validity period (default, configurable)
- Supports all major Nigerian banks

## Troubleshooting

### Common Issues

#### 1. Authentication Errors (401)

```
KoraPayError: Authentication failed - Invalid API key
```

**Solution**: Verify `KORAPAY_SECRET_KEY` is correct and not expired.

#### 2. Webhook Signature Verification Fails

```
Webhook signature verification failed
```

**Solution**: Ensure `KORAPAY_WEBHOOK_SECRET` matches dashboard.

#### 3. Network Timeouts

```
KoraPayError: Request timeout after 30 seconds
```

**Solution**: Check firewall rules, increase timeout if needed.

### Health Check

```bash
# Check KoraPay service health
curl https://api.onepay.ng/health | jq '.dependencies.korapay'

# Expected response:
{
  "status": "healthy",
  "mode": "production",
  "lastRequest": "2024-01-15T10:30:00Z",
  "errorRate": "0.02%"
}
```

## Migration from Quickteller

If migrating from Quickteller:

1. Keep Quickteller credentials as backup
2. Deploy with `KORAPAY_ENABLED=true`
3. Run in mock mode first to verify integration
4. Switch to live mode with `KORAPAY_USE_SANDBOX=false`
5. Monitor closely for first 24 hours

## Support

| Channel | Contact |
|---------|---------|
| KoraPay Support | support@korapay.com |
| KoraPay Documentation | https://docs.korapay.com |
| OnePay OnCall | See PagerDuty |

## Related Documentation

- [Rollback Procedures](ROLLBACK.md)
- [Disaster Recovery Plan](../scripts/disaster_recovery.py)
- [API Reference](../services/korapay.py)
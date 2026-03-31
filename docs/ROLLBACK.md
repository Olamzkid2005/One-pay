# KoraPay Rollback Procedures

This document provides step-by-step procedures for rolling back from KoraPay to Quickteller/Interswitch payment integration.

## Rollback Decision Criteria

Initiate a rollback when any of the following conditions are met:

| Condition | Threshold | Severity |
|-----------|-----------|----------|
| Error Rate | > 5% of transactions failing | Critical |
| SLA Violation | p95 latency > 5 seconds for > 5 minutes | Critical |
| Success Rate | < 95% for > 10 minutes | Critical |
| API Availability | < 99% uptime | Critical |
| Circuit Breaker | OPEN state for > 15 minutes | Critical |
| Revenue Impact | > ₦100,000 lost per hour | Critical |
| User Reports | > 50 complaints per hour | High |
| Webhook Failures | > 20% failure rate | High |

## Pre-Rollback Checklist

- [ ] Notify operations team via Slack/PagerDuty
- [ ] Notify finance team of potential impact
- [ ] Document incident ticket number
- [ ] Capture current metrics and error logs
- [ ] Verify Quickteller credentials are still valid
- [ ] Ensure database backup is recent (within last hour)
- [ ] Notify customer support team

## Rollback Procedures

### Automatic Rollback (Preferred)

If automatic rollback is enabled:

```bash
# Trigger automatic rollback based on error rate
python scripts/rollback_to_quickteller.py --trigger=error_rate --threshold=5

# Trigger automatic rollback based on SLA violation
python scripts/rollback_to_quickteller.py --trigger=sla_violation --threshold=5s
```

The automatic rollback script will:
1. Check rollback eligibility
2. Create a database backup
3. Restore Quickteller configuration
4. Verify rollback success
5. Send notification to operations

### Manual Rollback (Step-by-Step)

#### Step 1: Enable Quickteller Configuration

Set environment variables:

```bash
# .env.production
PAYMENT_PROVIDER=quickteller
QUICKTELLER_CLIENT_ID=your_client_id
QUICKTELLER_CLIENT_SECRET=your_client_secret
QUICKTELLER_BASE_URL=https://webpay.interswitchng.com
MERCHANT_CODE=your_merchant_code
PAYABLE_CODE=your_payable_code
KORAPAY_ENABLED=false
```

#### Step 2: Restore Database

```bash
# Restore from latest backup
psql -h db.example.com -U postgres -d onepay_production < backups/onetest_$(date +%Y%m%d_%H%M%S).sql

# Verify restoration
psql -h db.example.com -U postgres -d onepay_production -c "SELECT COUNT(*) FROM transactions WHERE created_at > NOW() - INTERVAL '1 hour';"
```

#### Step 3: Revert Code Changes

```bash
# Revert to previous deployment
git revert HEAD
git push origin main

# Or use Kubernetes rollback
kubectl rollout undo deployment/onepay-api
```

#### Step 4: Verify Rollback

```bash
# Check service is running
curl https://api.onepay.ng/health | jq '.status'

# Test payment flow in mock mode
curl -X POST https://api.onepay.ng/api/payment-link \
  -H "Content-Type: application/json" \
  -d '{"amount": 1000, "customer_reference": "TEST123"}'

# Verify Quickteller is active in logs
kubectl logs -f deployment/onepay-api | grep -i "quickteller"
```

## Post-Rollback Actions

### Immediate (0-30 minutes)

- [ ] Verify all transactions are processing
- [ ] Check error rates have returned to normal (< 1%)
- [ ] Monitor customer support tickets
- [ ] Notify stakeholders rollback is complete
- [ ] Update incident ticket with resolution details

### Short-term (1-24 hours)

- [ ] Review KoraPay failure root cause
- [ ] Document lessons learned
- [ ] Update runbook with new findings
- [ ] Schedule post-incident review meeting
- [ ] Consider KoraPay support escalation

### Long-term (1 week)

- [ ] Complete incident post-mortem
- [ ] Implement fixes for identified issues
- [ ] Plan next KoraPay integration attempt
- [ ] Update monitoring thresholds if needed
- [ ] Schedule follow-up with KoraPay technical team

## Quick Reference

| Action | Command |
|--------|---------|
| Check current provider | `grep PAYMENT_PROVIDER .env` |
| View rollback logs | `tail -f logs/rollback.log` |
| Check transaction status | `curl /api/transactions/status` |
| Emergency stop | `kubectl scale deployment/onepay-api --replicas=0` |

## Contact Information

| Role | Contact | Response Time |
|------|---------|---------------|
| KoraPay Support | support@korapay.com | < 4 hours |
| KoraPay Technical | tech@korapay.com | < 2 hours |
| Internal OnCall | See PagerDuty | < 15 minutes |
| Database Admin | dba@onepay.ng | < 30 minutes |

## Rollback Verification Commands

```bash
# Verify KoraPay is disabled
python -c "from services.korapay import korapay; print('KoraPay enabled:', korapay.is_configured())"

# Verify Quickteller is enabled
python -c "from services.quickteller import quickteller; print('Quickteller enabled:', quickteller.is_configured())"

# Check recent transaction success rate
SELECT 
  DATE_TRUNC('hour', created_at) as hour,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
  ROUND(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100, 2) as success_rate
FROM transactions 
WHERE created_at > NOW() - INTERVAL '4 hours'
GROUP BY hour
ORDER BY hour DESC;
```

## Related Documentation

- [KoraPay Setup Guide](KORAPAY_SETUP.md)
- [Disaster Recovery Plan](../scripts/disaster_recovery.py)
- [Deployment Procedures](../scripts/deploy.py)
- [Monitoring Dashboard](../grafana/dashboards/korapay-integration.json)
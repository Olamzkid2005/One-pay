---
inclusion: auto
---

# Monitoring Skill

Monitor OnePay health, metrics, and SLA compliance.

## When to Use
- User wants to check system health
- Investigating performance issues
- SLA monitoring

## Health Check Endpoint
```bash
curl http://localhost:5000/health
```

## Metrics Endpoint
```bash
curl http://localhost:5000/metrics
```

## Prometheus Alerts
- `prometheus/alerts/korapay.yml` - KoraPay-related alerts
- `prometheus/alerts/voicepay.yml` - VoicePay-related alerts

## SLA Monitoring
```bash
# Run SLA monitor tests
pytest tests/unit/test_sla_monitor.py -v
```

## Key Services
- `services/sla_monitor.py` - SLA tracking
- `services/security_monitor.py` - Security monitoring
- `services/cache.py` - Cache metrics

## Grafana Dashboards
Located in `grafana/` directory for import.

## Log Analysis
```bash
# Check recent errors
grep ERROR logs/*.log | tail -50

# Check payment-related logs
grep -i korapay logs/*.log | tail -20
```

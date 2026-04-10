# OnePay Implementation Plan - Phase 5: Operations & Monitoring

**Version:** 1.0  
**Created:** April 10, 2026  
**Status:** Active  
**Estimated Effort:** ~30 hours

---

## Overview

This document covers Phase 5 of the OnePay implementation plan: Operations & Monitoring. This phase includes 5 tasks focused on improving operational visibility, monitoring, and disaster recovery capabilities.

**Tasks in this phase:** 5
- OPS-001: Implement Structured JSON Logging (4h)
- OPS-002: Add Prometheus Metrics for Business Logic (6h)
- OPS-003: Implement Grafana Dashboards (8h)
- OPS-004: Add Automated Backup Verification (4h)
- OPS-005: Create Disaster Recovery Procedures (8h)

---

## OPS-001: Implement Structured JSON Logging

**Files:** `app.py`, config, all modules  
**Estimated Effort:** 4 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Install python-json-logger:
   ```bash
   pip install python-json-logger
   ```
2. Configure JSON logging in `app.py`:
   ```python
   from pythonjsonlogger import jsonlogger
   
   def setup_logging():
       log_handler = logging.StreamHandler()
       formatter = jsonlogger.JsonFormatter(
           '%(asctime)s %(name)s %(levelname)s %(message)s'
       )
       log_handler.setFormatter(formatter)
       logger.addHandler(log_handler)
       logger.setLevel(logging.INFO)
   ```
3. Add structured log fields:
   ```python
   logger.info("Transaction created", extra={
       "request_id": request_id,
       "user_id": user_id,
       "tx_ref": tx_ref,
       "amount": str(amount)
   })
   ```
4. Add configuration:
   ```python
   LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text")  # "json" or "text"
   ```

### Acceptance Criteria
- [ ] Logs output in JSON format in production
- [ ] Structured fields: timestamp, level, message, request_id, user_id
- [ ] Configurable format (JSON/text)
- [ ] No performance degradation

### Checkpoint Test
```bash
# Test JSON logging
export LOG_FORMAT=json
python -c "
from app import create_app
app = create_app()
app.logger.info('Test log message', extra={'request_id': 'test-123'})
" | jq .
# Expected: Valid JSON output
```

---

## OPS-002: Add Prometheus Metrics for Business Logic

**Files:** `blueprints/*.py`, `services/*.py`  
**Estimated Effort:** 6 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Install prometheus_client:
   ```bash
   pip install prometheus_client
   ```
2. Add metrics to `app.py`:
   ```python
   from prometheus_client import Counter, Histogram, Gauge, generate_latest
   
   # Define metrics
   transaction_counter = Counter(
       'transactions_total',
       'Total number of transactions',
       ['status', 'currency']
   )
   
   transaction_duration = Histogram(
       'transaction_duration_seconds',
       'Transaction processing duration'
   )
   
   active_users = Gauge(
       'active_users',
       'Number of active users'
   )
   ```
3. Add metrics endpoint:
   ```python
   @app.route("/metrics")
   def metrics():
       return generate_latest()
   ```
4. Add metrics to business logic:
   ```python
   @transaction_duration.time()
   def create_transaction(...):
       transaction_counter.labels(status='pending', currency='NGN').inc()
       # Implementation
   ```

### Acceptance Criteria
- [ ] Metrics endpoint accessible at `/metrics`
- [ ] Transaction volume tracked
- [ ] Success rate calculated
- [ ] Response times measured
- [ ] Cache hit rate tracked

### Checkpoint Test
```bash
# Test metrics endpoint
curl http://localhost:5000/metrics
# Expected: Prometheus metrics output
```

---

## OPS-003: Implement Grafana Dashboards

**Files:** `grafana/dashboards/`  
**Estimated Effort:** 8 hours  
**Dependencies:** OPS-002  
**Risk:** Medium

### Implementation Steps

1. Create dashboard directory:
   ```bash
   mkdir -p grafana/dashboards
   ```
2. Create business metrics dashboard:
   ```json
   {
     "dashboard": {
       "title": "OnePay Business Metrics",
       "panels": [
         {
           "title": "Transaction Volume",
           "targets": [
             {
               "expr": "rate(transactions_total[5m])"
             }
           ]
         },
         {
           "title": "Success Rate",
           "targets": [
             {
               "expr": "rate(transactions_total{status=\"verified\"}[5m]) / rate(transactions_total[5m])"
             }
           ]
         }
       ]
     }
   }
   ```
3. Create system health dashboard
4. Create security events dashboard
5. Import dashboards to Grafana

### Acceptance Criteria
- [ ] Business metrics dashboard displays transaction volume
- [ ] System health dashboard shows resource usage
- [ ] Security dashboard shows alert counts
- [ ] Dashboards auto-refresh
- [ ] Alert thresholds configured

### Checkpoint Test
```bash
# Verify dashboard files exist
ls grafana/dashboards/
# Expected: Dashboard JSON files present
```

---

## OPS-004: Add Automated Backup Verification

**File:** `scripts/verify_backup.py` (new)  
**Estimated Effort:** 4 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Create backup verification script:
   ```python
   # scripts/verify_backup.py
   import subprocess
   import logging
   
   def verify_backup():
       """Verify backup integrity"""
       # Restore backup to test database
       subprocess.run([
           "pg_restore",
           "--clean",
           "--no-acl",
           "--no-owner",
           "-d", "onepay_test",
           "/backups/latest.dump"
       ])
       
       # Verify table counts
       from database import get_db
       with get_db() as db:
           from models.transaction import Transaction
           from models.user import User
           
           tx_count = db.query(Transaction).count()
           user_count = db.query(User).count()
           
           if tx_count == 0 or user_count == 0:
               logging.error("Backup verification failed: empty tables")
               return False
           
           logging.info(f"Backup verified: {tx_count} transactions, {user_count} users")
           return True
   
   if __name__ == "__main__":
       verify_backup()
   ```
2. Add to cron:
   ```cron
   0 2 * * * /usr/bin/python3 /app/scripts/verify_backup.py
   ```
3. Add alert on failure

### Acceptance Criteria
- [ ] Backup restored to test database
- [ ] Table counts verified
- [ ] Data integrity checked
- [ ] Alerts sent on failure
- [ ] Daily verification scheduled

### Checkpoint Test
```bash
# Test backup verification
python scripts/verify_backup.py
# Expected: Backup verification successful
```

---

## OPS-005: Create Disaster Recovery Procedures

**File:** `docs/DISASTER_RECOVERY.md` (new)  
**Estimated Effort:** 8 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Create disaster recovery document:
   ```markdown
   # Disaster Recovery Procedures
   
   ## Backup Strategy
   - Daily full backups at 2 AM UTC
   - Retention: 7 daily, 4 weekly, 12 monthly
   - Storage: S3 with encryption
   
   ## Restore Procedures
   ### Database Restore
   1. Stop application
   2. Restore from backup: `pg_restore -d onepay latest.dump`
   3. Verify data integrity
   4. Start application
   
   ### Application Restore
   1. Deploy from Docker image
   2. Restore configuration
   3. Start services
   
   ## Failover Procedures
   ### Database Failover
   1. Promote standby to primary
   2. Update connection strings
   3. Verify replication
   
   ## Contact Information
   - Primary: admin@yourdomain.com
   - Emergency: +1-XXX-XXX-XXXX
   ```

### Acceptance Criteria
- [ ] Backup strategy documented
- [ ] Restore procedures documented
- [ ] Failover procedures documented
- [ ] Contact information updated
- [ ] DR procedures tested quarterly

### Checkpoint Test
```bash
# Verify DR documentation exists
ls docs/DISASTER_RECOVERY.md
# Expected: File exists
```

---

## Phase 5 Checkpoint Test

```bash
#!/bin/bash
# Phase 5 Operations Checkpoint Test

echo "=== Phase 5 Operations Checkpoint ==="
echo ""

echo "1. Testing JSON Logging..."
export LOG_FORMAT=json
python -c "
from app import create_app
app = create_app()
app.logger.info('Test log message', extra={'request_id': 'test-123'})
" | jq . > /dev/null 2>&1 && echo "✓ JSON logging working" || echo "✗ JSON logging failed"

echo "2. Testing Prometheus Metrics..."
curl -s http://localhost:5000/metrics | grep -q "transactions_total" && echo "✓ Metrics endpoint working" || echo "✗ Metrics endpoint not working"

echo "3. Testing Grafana Dashboards..."
ls grafana/dashboards/ | grep -q ".json" && echo "✓ Dashboard files present" || echo "✗ Dashboard files missing"

echo "4. Testing Backup Verification..."
python scripts/verify_backup.py && echo "✓ Backup verification working" || echo "⚠ Backup verification not configured"

echo "5. Testing DR Documentation..."
ls docs/DISASTER_RECOVERY.md && echo "✓ DR documentation exists" || echo "✗ DR documentation missing"

echo ""
echo "=== Phase 5 Checkpoint Complete ==="
```

---

## Phase 5 Summary

**Total Tasks:** 5  
**Total Estimated Effort:** ~30 hours  
**Risk Profile:** 4 Low, 1 Medium  
**Dependencies:** 1 internal (OPS-003 depends on OPS-002)

**Completion Criteria:**
- All 5 checkpoint tests pass
- JSON logging operational
- Prometheus metrics accessible
- Grafana dashboards configured
- Backup verification automated
- DR procedures documented

**Next Phase:** Phase 6 - Documentation
